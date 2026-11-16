import { test, expect } from "@playwright/test";
import { mkdtemp, mkdir, readFile, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import path from "node:path";
import { Canvas } from "./canvas.js";
import {
  launchDesktop,
  projectPicker,
  closeTemporaryDesktop,
} from "./desktop.js";

test("direct chart presets, phase layout, compile and saved reopen", async ({}, testInfo) => {
  test.setTimeout(90000);
  const directory = await mkdtemp(path.join(tmpdir(), "easyai-direct-plots-"));
  const projectDirectory = path.join(directory, "project");
  const state = path.join(directory, "state");
  await mkdir(projectDirectory);
  let app = await launchDesktop(state);
  let ownedProcess = app.process();
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
    await page.getByRole("tab", { name: "训练管线", exact: true }).click();
    const canvas = new Canvas(page, "训练管线");
    await expect(canvas.block("before-figure")).toHaveCount(0);
    await expect(canvas.block("before-0-panel")).toHaveCount(1);
    await canvas.clickField(
      canvas.block("before-0-panel").locator("text").first(),
      "select direct chart",
      canvas.block("before-0-panel"),
    );
    const inspector = page.getByRole("region", {
      name: "训练前 · 图表布局",
      exact: true,
    });
    await expect(inspector).toContainText("1 个图表，排列为 1 行 1 列");

    // Real pointer drag of the preconfigured sample chart into the phase chain.
    await canvas.reveal(
      canvas.block("before-0-panel").locator("text").first(),
      true,
    );
    const target = await canvas.connection("before-0-panel", "next");
    await canvas.panel
      .getByRole("treeitem", { name: "图表", exact: true })
      .click();
    const flyout = canvas.panel.locator(
      ".blocklyFlyout .blocklyBlockCanvas > g[data-id]",
    );
    await expect(flyout.filter({ hasText: "创建画布" })).toHaveCount(0);
    await expect(flyout.filter({ hasText: "保存图像" })).toHaveCount(0);
    const preset = flyout
      .filter({ hasText: "绘制图表" })
      .filter({ hasText: "train_samples" });
    await expect(preset).toHaveCount(1);
    const blockPath = preset.locator(":scope > path.blocklyPath");
    const box = (await blockPath.boundingBox())!;
    const scale = await blockPath.evaluate((element) =>
      Math.abs((element as SVGPathElement).getScreenCTM()!.a),
    );
    await page.mouse.move(box.x + 8, box.y + 10);
    await page.mouse.down();
    try {
      await page.mouse.move(box.x + 20, box.y + 14, { steps: 5 });
      await page.mouse.move(target.x + 8 - 15 * scale, target.y + 10, {
        steps: 20,
      });
    } finally {
      await page.mouse.up();
    }
    const snapshot = async () =>
      JSON.parse(
        await readFile(
          path.join(projectDirectory, "project.easyai.json"),
          "utf8",
        ),
      );
    await expect
      .poll(
        async () =>
          (await snapshot()).workspaces.training.blocks.blocks[0].inputs.before
            .block.next?.block.type,
      )
      .toBe("viz.panel");
    await expect(inspector).toContainText("2 个图表，排列为 1 行 2 列");
    await inspector.getByLabel("排列方式").selectOption("2,2");
    await inspector.getByLabel("图片尺寸").selectOption("large");
    await inspector.getByRole("button", { name: "应用图表设置" }).click();
    await expect(inspector).toContainText("2 个图表，排列为 2 行 2 列");
    await expect
      .poll(
        async () =>
          (await snapshot()).workspaces.training.blocks.blocks[0].fields
            .BEFORE_LAYOUT,
      )
      .toBe("2,2");
    await page.getByRole("button", { name: "检查与编译", exact: true }).click();
    await expect(
      page.getByRole("status").filter({ hasText: /^代码检查通过/ }),
    ).toBeVisible();
    await page.screenshot({ path: testInfo.outputPath("direct-plots.png") });
    const saved = await snapshot();
    await closeTemporaryDesktop(app, false);
    app = await launchDesktop(state);
    ownedProcess = app.process();
    const reopened = await app.firstWindow();
    await expect(reopened.getByTestId("backend-status")).toHaveText(
      "本地服务已就绪。",
    );
    await reopened.getByRole("tab", { name: "训练管线", exact: true }).click();
    const restored = new Canvas(reopened, "训练管线");
    await restored.clickField(
      restored.block("before-0-panel").locator("text").first(),
      "select reopened chart",
      restored.block("before-0-panel"),
    );
    const restoredInspector = reopened.getByRole("region", {
      name: "训练前 · 图表布局",
      exact: true,
    });
    await expect(restoredInspector.getByLabel("排列方式")).toHaveValue("2,2");
    await expect(restoredInspector.getByLabel("图片尺寸")).toHaveValue("large");
    expect((await snapshot()).workspaces).toEqual(saved.workspaces);
    await reopened
      .getByRole("button", { name: "检查与编译", exact: true })
      .click();
    await expect(
      reopened.getByRole("status").filter({ hasText: /^代码检查通过/ }),
    ).toBeVisible();
  } catch (error) {
    console.error("DIRECT_PLOTS_FAILURE", error);
    failed = true;
    throw error;
  } finally {
    if (ownedProcess.exitCode === null && ownedProcess.signalCode === null)
      await closeTemporaryDesktop(app, failed);
    else {
      expect(ownedProcess.exitCode).toBe(0);
      expect(ownedProcess.signalCode).toBeNull();
    }
    await rm(directory, { recursive: true, force: true });
  }
});
