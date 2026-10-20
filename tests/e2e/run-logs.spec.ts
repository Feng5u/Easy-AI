import { test, expect, type Locator } from "@playwright/test";
import { execFile } from "node:child_process";
import { promisify } from "node:util";
import { appendFile, mkdtemp, readFile, rm, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import path from "node:path";
import { launchDesktop, closeTemporaryDesktop } from "./desktop.js";
import type { DesktopAPI } from "../../apps/desktop/electron/bridge.js";

const PAGE = 32768;

async function geometry(viewport: Locator) {
  return viewport.evaluate((host) => {
    const box = host.getBoundingClientRect();
    const rows = [...host.querySelectorAll<HTMLElement>(".run-log-row")];
    const last = rows.at(-1)!;
    return {
      count: rows.length,
      rowHeight: rows.every((row) => row.getBoundingClientRect().height === 20),
      lineHeight: rows.every(
        (row) => getComputedStyle(row).lineHeight === "20px",
      ),
      horizontal: host.scrollWidth > host.clientWidth,
      clientHeight: host.clientHeight,
      atBottom:
        Math.abs(host.scrollHeight - host.clientHeight - host.scrollTop) < 1,
      lastVisible:
        last.getBoundingClientRect().bottom <=
        box.top + host.clientTop + host.clientHeight + 1,
      lastText: last.textContent,
    };
  });
}

test("real log windows and image history preserve their independent views", async ({}, testInfo) => {
  test.setTimeout(120000);
  const directory = await mkdtemp(path.join(tmpdir(), "easyai-log-e2e-"));
  // Only test-owned files feed the real saved-run / IPC / read_log path. No
  // Runner, training environment, dataset, metrics or process is synthesized.
  const { stdout } = await promisify(execFile)(
    "uv",
    [
      "run",
      "--frozen",
      "--project",
      "services/backend",
      "python",
      path.resolve("tests/e2e/seed-log-run.py"),
      directory,
    ],
    { timeout: 15000 },
  );
  const fixture = JSON.parse(stdout) as {
    runId: string;
    runRoot: string;
    figureIds: string[];
    figureSources: { producer: string; contributors: string[] }[];
  };
  const projectFile = path.join(directory, "project/project.easyai.json");
  const snapshotFile = path.join(
    fixture.runRoot,
    "snapshot/project.easyai.json",
  );
  const savedProject = await readFile(projectFile, "utf8");
  const savedSnapshot = await readFile(snapshotFile, "utf8");
  const outFile = path.join(fixture.runRoot, "logs/train.log");
  const errFile = path.join(fixture.runRoot, "logs/stderr.log");
  const head = Buffer.from("FIXTURE-HEAD\n");
  const initial = Buffer.concat([
    head,
    Buffer.alloc(PAGE - head.length - 1, 10),
    Buffer.from("\r\n中文😀\n"), // CRLF split across pages; many blank rows.
    Buffer.from(("W".repeat(256) + "\n").repeat(600)),
    Buffer.from("FIXTURE-LIVE-END"),
  ]);
  await writeFile(outFile, initial);
  await writeFile(errFile, "FIXTURE-STDERR\n");
  const stateDirectory = path.join(directory, "application-state");
  let app = await launchDesktop(stateDirectory);
  let failed = false;
  try {
    const page = await app.firstWindow();
    const failures: string[] = [];
    page.on("pageerror", (error) => failures.push(error.name));
    await expect(page.getByTestId("backend-status")).toHaveText(
      "本地服务已就绪。",
    );
    await page
      .getByRole("button", {
        name: new RegExp(`^${fixture.runId.slice(0, 8)} ·`),
      })
      .click();
    const image = page.locator(".image-preview img");
    const pixel = () =>
      image.evaluate((element) => {
        const picture = element as HTMLImageElement;
        if (
          !picture.complete ||
          picture.naturalWidth !== 1 ||
          picture.naturalHeight !== 1
        )
          return null;
        const canvas = document.createElement("canvas");
        canvas.width = canvas.height = 1;
        const context = canvas.getContext("2d")!;
        context.drawImage(picture, 0, 0);
        return [...context.getImageData(0, 0, 1, 1).data];
      });
    await expect(image).toHaveAttribute("alt", /fixture-image-1\.png/);
    await expect.poll(pixel).toEqual([30, 80, 210, 255]);
    const latestArtifact = page
      .locator(".artifacts > li")
      .filter({ hasText: "outputs/fixture-image-1.png" });
    const source = page.getByRole("region", {
      name: "本次运行的代码与积木来源",
      exact: true,
    });
    const snapshot = source.getByRole("region", {
      name: "本次运行的只读积木快照",
      exact: true,
    });
    const mapping = fixture.figureSources[1];
    const assertSelected = async (id: string) => {
      await expect(snapshot.getByLabel("所选积木 ID")).toHaveText(id);
      await expect(
        snapshot.getByRole("tab", { name: "训练管线", exact: true }),
      ).toHaveAttribute("aria-selected", "true");
      await expect
        .poll(() =>
          source
            .locator(".code-selected button")
            .evaluateAll(
              (buttons, blockId) =>
                buttons.some((button) =>
                  button
                    .getAttribute("aria-label")
                    ?.endsWith(`源积木 ${blockId}`),
                ),
              id,
            ),
        )
        .toBe(true);
    };
    await latestArtifact
      .getByRole("button", { name: `来源：${mapping.producer}`, exact: true })
      .click();
    await assertSelected(mapping.producer);
    await source.locator("summary").first().click();
    await expect(source.locator("details").first()).not.toHaveAttribute("open");
    await latestArtifact
      .getByRole("button", { name: `来源：${mapping.producer}`, exact: true })
      .click();
    await expect(source.locator("details").first()).toHaveAttribute("open", "");
    await expect(snapshot).toBeVisible();
    await assertSelected(mapping.producer);
    const assertPainted = async (id: string) => {
      const selected = snapshot
        .getByRole("tabpanel", { name: "训练管线", exact: true })
        .locator("g.blocklyHighlighted")
        .first();
      await expect(selected).toHaveAttribute("data-id", id);
      await selected.scrollIntoViewIfNeeded();
      await expect(selected).toBeInViewport();
      const monaco = source.getByLabel("Monaco 只读代码视图");
      await monaco.scrollIntoViewIfNeeded();
      await expect(
        monaco.locator(".monaco-source-selected-semantic").first(),
      ).toBeInViewport();
    };
    await assertPainted(mapping.producer);
    const monaco = source.getByLabel("Monaco 只读代码视图");
    const codeInput = monaco.getByRole("textbox");
    await codeInput.focus();
    await expect(codeInput).toBeFocused();
    await codeInput.press("ControlOrMeta+Home");
    // Monaco virtualizes scrolling; native element.scrollTop is not its position.
    const firstLine = monaco.locator(".view-lines > .view-line").first();
    await expect(firstLine).toContainText("Generated by Easy-AI");
    await expect(firstLine).toBeInViewport();
    await expect(
      monaco.locator(".monaco-source-selected-semantic").first(),
    ).not.toBeInViewport();
    await latestArtifact
      .getByRole("button", { name: `来源：${mapping.producer}`, exact: true })
      .click();
    await assertPainted(mapping.producer);
    await latestArtifact
      .getByRole("button", { name: "查看配置", exact: true })
      .click();
    const choices = latestArtifact.locator(".artifact-contributors button");
    await expect(choices).toHaveCount(mapping.contributors.length);
    expect(mapping.contributors.length).toBeGreaterThan(1);
    for (const [index, id] of mapping.contributors.entries()) {
      await choices.nth(index).click();
      await assertSelected(id);
    }
    await assertPainted(mapping.contributors.at(-1)!);
    // An explicit repeated source click must navigate back after a manual tab change.
    await snapshot.getByRole("tab", { name: "模型结构", exact: true }).click();
    await latestArtifact
      .getByRole("button", { name: `来源：${mapping.producer}`, exact: true })
      .click();
    await assertSelected(mapping.producer);
    await snapshot
      .getByRole("button", { name: "关闭快照，返回运行结果", exact: true })
      .click();
    await expect(snapshot).toHaveCount(0);
    await page
      .getByRole("combobox", { name: "运行图像版本" })
      .selectOption(fixture.figureIds[0]);
    await expect(image).toHaveAttribute("alt", /fixture-image-0\.png/);
    await expect.poll(pixel).toEqual([200, 60, 60, 255]);
    await page
      .getByRole("button", { name: "恢复最新图片", exact: true })
      .click();
    await expect(image).toHaveAttribute("alt", /fixture-image-1\.png/);
    await expect.poll(pixel).toEqual([30, 80, 210, 255]);
    const out = page.getByRole("region", { name: "stdout 日志查看器" });
    const err = page.getByRole("region", { name: "stderr 日志查看器" });
    const viewport = out.getByRole("list", { name: "stdout 虚拟文本窗口" });
    await expect(viewport).toContainText("FIXTURE-LIVE-END", {
      timeout: 15000,
    });
    await expect
      .poll(() => geometry(viewport))
      .toMatchObject({
        rowHeight: true,
        lineHeight: true,
        horizontal: true,
        atBottom: true,
        lastVisible: true,
        lastText: "FIXTURE-LIVE-END",
      });
    const measured = await geometry(viewport);
    expect(measured.count).toBeLessThanOrEqual(24);
    // The Windows classic horizontal scrollbar must consume viewport height;
    // this is the geometry that the old constant-height tail calculation missed.
    if (process.platform === "win32")
      expect(measured.clientHeight).toBeLessThan(320);
    await out
      .getByRole("button", { name: "暂停自动滚动 stdout", exact: true })
      .click();
    const pinned = await viewport.textContent();
    const grown = Buffer.from("\nFIXTURE-GROWN\n");
    await appendFile(outFile, grown);
    await appendFile(errFile, "FIXTURE-ERR-GROWN\n");
    await expect(err.getByRole("list")).toContainText("FIXTURE-ERR-GROWN");
    await expect(out).toContainText("字节已被实时读取");
    expect(await viewport.textContent()).toBe(pinned);
    await out
      .getByRole("button", { name: "从头查看 stdout", exact: true })
      .click();
    await expect(out).toContainText("历史页：显示字节 [0, 32,768)");
    await expect(viewport).toContainText("FIXTURE-HEAD");
    await expect(viewport.getByRole("listitem")).toHaveCount(20);
    await out
      .getByRole("button", { name: "下一页 stdout", exact: true })
      .click();
    await expect(viewport).toContainText("中文😀");
    await out
      .getByRole("button", { name: "上一页 stdout", exact: true })
      .click();
    await expect(viewport).toContainText("FIXTURE-HEAD");
    await out
      .getByRole("button", { name: "恢复实时 stdout", exact: true })
      .click();
    await expect(viewport).toContainText("FIXTURE-GROWN");
    await viewport.focus();
    await viewport.press("Home");
    await expect
      .poll(() => viewport.evaluate((host) => host.scrollTop))
      .toBe(0);
    expect(await viewport.getByRole("listitem").count()).toBeLessThanOrEqual(
      24,
    );
    await viewport.evaluate((host) => {
      host.scrollLeft = host.scrollWidth;
    });
    await expect
      .poll(() => viewport.evaluate((host) => host.scrollLeft))
      .toBeGreaterThan(0);
    await viewport.press("End");
    await expect
      .poll(() => geometry(viewport))
      .toMatchObject({ atBottom: true, lastVisible: true });
    await viewport.evaluate((host) => {
      host.scrollLeft = 0;
    });
    // A pending UTF-8 suffix advances only after the terminal contract flushes
    // it as replacement text. Cancelling CREATED cannot launch any subprocess.
    await appendFile(outFile, Buffer.from([0xe4, 0xb8]));
    await page
      .getByRole("button", { name: "停止本次运行", exact: true })
      .click();
    await expect(viewport).toContainText("�");
    await expect(out).toContainText(
      `实时已读取至 ${(initial.length + grown.length + 2).toLocaleString("en-US")} 字节`,
    );
    await testInfo.attach("log-geometry", {
      body: JSON.stringify(await geometry(viewport)),
      contentType: "application/json",
    });
    await testInfo.attach("log-window", {
      body: await viewport.screenshot(),
      contentType: "image/png",
    });
    const events = await readFile(
      path.join(fixture.runRoot, "logs/events.jsonl"),
      "utf8",
    );
    expect(events).not.toMatch(/process_spawn|runtime_started|epoch_completed/);
    expect(failures).toEqual([]);
    expect(await readFile(projectFile, "utf8")).toBe(savedProject);
    expect(await readFile(snapshotFile, "utf8")).toBe(savedSnapshot);
    await closeTemporaryDesktop(app, false);
    app = await launchDesktop(stateDirectory);
    const reopened = await app.firstWindow();
    reopened.on("pageerror", (error) => failures.push(error.name));
    await expect(reopened.getByTestId("backend-status")).toHaveText(
      "本地服务已就绪。",
    );
    await reopened
      .getByRole("button", {
        name: new RegExp(`^${fixture.runId.slice(0, 8)} ·`),
      })
      .click();
    await expect(reopened.locator(".run-summary")).toContainText("已停止");
    await expect(reopened.locator(".image-preview img")).toHaveAttribute(
      "alt",
      /fixture-image-1\.png/,
    );
    await expect(
      reopened
        .getByRole("region", { name: "stdout 日志查看器" })
        .getByRole("list"),
    ).toContainText("FIXTURE-GROWN", { timeout: 15000 });
    await expect(
      reopened.getByRole("region", {
        name: "本次运行的只读积木快照",
        exact: true,
      }),
    ).toHaveCount(0);
    expect(await readFile(projectFile, "utf8")).toBe(savedProject);
    expect(await readFile(snapshotFile, "utf8")).toBe(savedSnapshot);
    expect(failures).toEqual([]);
  } catch (error) {
    failed = true;
    throw error;
  } finally {
    let closed = false;
    try {
      if (failed)
        await (
          await app.firstWindow()
        ).evaluate(async (runId) => {
          const api = (window as unknown as { easyai: DesktopAPI }).easyai;
          // Only this test's unstarted run; never abandon an active-run dialog.
          await api.runs.cancel(runId);
        }, fixture.runId);
      await closeTemporaryDesktop(app, failed);
      closed = true;
    } catch (error) {
      console.error("EASYAI_LOG_CLOSE_FAILED");
      if (!failed) throw error;
    }
    if (closed) await rm(directory, { recursive: true });
  }
});
