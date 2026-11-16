import { test, expect, type ElectronApplication } from "@playwright/test";
import { mkdtemp, mkdir, readFile, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import path from "node:path";
import { Canvas } from "./canvas.js";
import {
  launchDesktop,
  projectPicker,
  closeTemporaryDesktop,
} from "./desktop.js";

// Exercise Electron's native accelerator path, not only a DOM-dispatched event.
async function shortcut(app: ElectronApplication, key: string, shift = false) {
  await app.evaluate(
    ({ BrowserWindow }, { key, shift }) => {
      const contents = BrowserWindow.getAllWindows()[0].webContents;
      const modifiers: ("control" | "shift")[] = shift
        ? ["control", "shift"]
        : ["control"];
      contents.sendInputEvent({ type: "keyDown", keyCode: key, modifiers });
      contents.sendInputEvent({ type: "keyUp", keyCode: key, modifiers });
    },
    { key, shift },
  );
}

test("Ctrl zoom changes only the focused Blockly canvas and preserves the project", async ({}, testInfo) => {
  test.setTimeout(60000);
  const directory = await mkdtemp(path.join(tmpdir(), "easyai-zoom-e2e-"));
  const projectDirectory = path.join(directory, "project");
  await mkdir(projectDirectory);
  const app = await launchDesktop(path.join(directory, "application-state"));
  let failed = false;
  try {
    const page = await app.firstWindow();
    await expect(page.getByTestId("backend-status")).toHaveText(
      "本地服务已就绪。",
    );
    await projectPicker(app, projectDirectory);
    await page
      .getByRole("button", { name: "新建 MNIST 示例", exact: true })
      .click();
    await expect(
      page.locator(".project-editor-canvas .blocklySvg"),
    ).toHaveCount(3);
    const projectPath = path.join(projectDirectory, "project.easyai.json");
    const saved = JSON.parse(await readFile(projectPath, "utf8"));
    const scales = () =>
      page
        .locator(
          ".project-editor-canvas .blocklySvg > .blocklyWorkspace > .blocklyBlockCanvas",
        )
        .evaluateAll((elements) =>
          elements.map(
            (element) =>
              element.getAttribute("transform")?.match(/scale\(([^)]+)\)/)?.[1],
          ),
        );
    const focusCanvas = async (name: string) => {
      await page.getByRole("tab", { name, exact: true }).click();
      await page
        .getByRole("tabpanel", { name, exact: true })
        .locator(".blocklySvg")
        .click({ position: { x: 300, y: 250 } });
      await expect
        .poll(() =>
          page.evaluate(() =>
            document.activeElement
              ?.closest(".project-editor-canvas")
              ?.getAttribute("aria-label"),
          ),
        )
        .toBe(name);
    };
    await focusCanvas("数据处理");
    const initial = await scales();
    expect(initial).toHaveLength(3);
    expect(initial.every((scale) => scale === "0.8")).toBe(true);
    await shortcut(app, "=");
    await expect
      .poll(async () => Number((await scales())[0]))
      .toBeGreaterThan(0.8);
    expect((await scales()).slice(1)).toEqual(initial.slice(1));
    await shortcut(app, "-");
    await expect.poll(async () => Number((await scales())[0])).toBeCloseTo(0.8);
    await shortcut(app, "+", true);
    await expect
      .poll(async () => Number((await scales())[0]))
      .toBeGreaterThan(0.8);
    await shortcut(app, "0");
    await expect.poll(scales).toEqual(initial);
    await page.keyboard.press("Control+NumpadAdd");
    await expect
      .poll(async () => Number((await scales())[0]))
      .toBeGreaterThan(0.8);
    await page.keyboard.press("Control+NumpadSubtract");
    await expect.poll(async () => Number((await scales())[0])).toBeCloseTo(0.8);
    await shortcut(app, "0");
    for (const [name, index] of [
      ["模型结构", 1],
      ["训练管线", 2],
    ] as const) {
      await focusCanvas(name);
      await shortcut(app, "-");
      await expect
        .poll(async () => Number((await scales())[index]))
        .toBeLessThan(0.8);
      await shortcut(app, "0");
      await expect.poll(scales).toEqual(initial);
    }
    await focusCanvas("数据处理");
    for (let i = 0; i < 15; i++) await shortcut(app, "=");
    await expect.poll(async () => Number((await scales())[0])).toBe(1.5);
    for (let i = 0; i < 25; i++) await shortcut(app, "-");
    await expect.poll(async () => Number((await scales())[0])).toBe(0.3);
    await shortcut(app, "0");
    await expect.poll(scales).toEqual(initial);
    // Typing a negative normalization value must remain a text edit.
    const canvas = new Canvas(page, "数据处理");
    await canvas.clickField(
      canvas.field("normalize", "MEAN"),
      "edit normalization mean",
    );
    const input = page.locator(".blocklyHtmlInput");
    await expect(input).toBeVisible();
    const value = await input.inputValue();
    await shortcut(app, "-");
    await expect.poll(scales).toEqual(initial);
    await expect(input).toHaveValue(value);
    await input.press("Control+a");
    await page.keyboard.type("-0.1");
    await expect(input).toHaveValue("-0.1");
    await input.fill(value);
    await input.press("Enter");
    expect(
      await app.evaluate(({ BrowserWindow }) =>
        BrowserWindow.getAllWindows()[0].webContents.getZoomFactor(),
      ),
    ).toBe(1);
    await expect(
      page.getByRole("button", { name: "保存工程配置", exact: true }),
    ).toBeDisabled();
    expect(JSON.parse(await readFile(projectPath, "utf8")).workspaces).toEqual(
      saved.workspaces,
    );
    await page.screenshot({ path: testInfo.outputPath("zoom-verified.png") });
  } catch (error) {
    failed = true;
    console.error(error);
    await (
      await app.firstWindow()
    ).screenshot({ path: testInfo.outputPath("zoom-failure.png") });
    throw error;
  } finally {
    await closeTemporaryDesktop(app, failed);
    await rm(directory, { recursive: true, force: true });
  }
});
