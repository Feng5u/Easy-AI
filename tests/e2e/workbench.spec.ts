import { test, expect } from "@playwright/test";
import { mkdtemp, mkdir, readFile, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import path from "node:path";
import {
  launchDesktop,
  projectPicker,
  closeTemporaryDesktop,
} from "./desktop.js";

test("workbench panels retain the real Blockly canvases and fill the desktop", async ({}, testInfo) => {
  test.setTimeout(60000);
  const directory = await mkdtemp(path.join(tmpdir(), "easyai-workbench-e2e-"));
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
    const canvases = page.locator(".project-editor-canvas .blocklySvg");
    await expect(canvases).toHaveCount(3);
    const originalCanvas = await canvases.first().elementHandle();
    const saved = JSON.parse(
      await readFile(
        path.join(projectDirectory, "project.easyai.json"),
        "utf8",
      ),
    );
    await page.getByRole("tab", { name: "模型结构", exact: true }).click();
    await page.getByRole("button", { name: "环境与数据", exact: true }).click();
    await expect(page.locator("#environment-heading")).toBeVisible();
    await page.getByRole("button", { name: "工程", exact: true }).click();
    await expect(page.locator("#project-heading")).toBeVisible();
    await page.getByRole("button", { name: "返回积木", exact: true }).click();
    await expect(
      page.getByRole("tab", { name: "模型结构", exact: true }),
    ).toHaveAttribute("aria-selected", "true");
    expect(
      await originalCanvas!.evaluate(
        (node) =>
          node === document.querySelector(".project-editor-canvas .blocklySvg"),
      ),
    ).toBe(true);
    const inspector = page.getByRole("complementary", {
      name: "对象注册与引用",
    });
    await page.getByRole("button", { name: "对象与参数", exact: true }).click();
    await expect(inspector).toBeHidden();
    await page.getByRole("button", { name: "对象与参数", exact: true }).click();
    await expect(inspector).toBeVisible();
    await page.getByRole("button", { name: "代码对照", exact: true }).click();
    await expect(
      page.getByLabel("Monaco 只读代码视图").locator(".monaco-editor"),
    ).toBeVisible();
    await expect(
      page.getByRole("button", { name: "开始本次运行", exact: true }),
    ).toBeDisabled();
    await expect
      .poll(async () => {
        const current = JSON.parse(
          await readFile(
            path.join(projectDirectory, "project.easyai.json"),
            "utf8",
          ),
        );
        return {
          workspaces: current.workspaces,
          codeVisible: current.ui.codeVisible,
        };
      })
      .toEqual({ workspaces: saved.workspaces, codeVisible: true });
    expect(
      await page.locator(".workbench-shell").evaluate((element) => {
        const box = element.getBoundingClientRect();
        return {
          x: box.x,
          y: box.y,
          width: box.width === innerWidth,
          height: box.height === innerHeight,
          overflow: document.documentElement.scrollHeight > innerHeight,
        };
      }),
    ).toEqual({ x: 0, y: 0, width: true, height: true, overflow: false });
    await page.screenshot({ path: testInfo.outputPath("workbench-code.png") });
    await page
      .getByRole("button", { name: "打开离线教程", exact: true })
      .click();
    await expect(
      page.getByRole("region", { name: "离线教程", exact: true }),
    ).toBeVisible();
    await expect(page.getByLabel("当前工程代码对照")).toBeHidden();
    await page
      .getByRole("button", { name: "关闭学习面板", exact: true })
      .click();
    await expect(page.getByLabel("当前工程代码对照")).toBeVisible();
    await page.getByRole("button", { name: "积木", exact: true }).click();
    await page.getByRole("tab", { name: "运行记录", exact: true }).click();
    await expect(
      page.getByText("暂无运行记录。", { exact: true }),
    ).toBeVisible();
    await page.getByRole("tab", { name: "日志与结果", exact: true }).click();
    await expect(
      page.getByText(
        "尚未开始训练。训练产生的日志、指标、图像和文件会显示在这里。",
        { exact: true },
      ),
    ).toBeVisible();
    await page.getByRole("button", { name: "收起面板", exact: true }).click();
    await page.screenshot({
      path: testInfo.outputPath("workbench-blocks.png"),
    });
    await expect(
      page.getByRole("button", { name: "保存工程配置", exact: true }),
    ).toBeDisabled();
  } catch (error) {
    failed = true;
    const page = await app.firstWindow();
    await page.screenshot({
      path: testInfo.outputPath("workbench-failure.png"),
    });
    throw error;
  } finally {
    await closeTemporaryDesktop(app, failed);
    await rm(directory, { recursive: true, force: true });
  }
});
