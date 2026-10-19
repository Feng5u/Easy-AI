import { test, expect, type ElectronApplication } from "@playwright/test";
import { mkdtemp, mkdir, readFile, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import path from "node:path";
import { Canvas, interaction } from "./canvas.js";
import {
  launchDesktop,
  projectPicker,
  closeTemporaryDesktop,
  observeTemporaryDesktop,
} from "./desktop.js";
import type * as Blockly from "blockly/core";
import type { ProjectDocument } from "../../apps/desktop/electron/bridge.js";

function savedBlock(value: unknown): Blockly.serialization.blocks.State {
  expect(value).toHaveProperty("type", expect.any(String));
  expect(value).toHaveProperty("id", expect.any(String));
  return value as Blockly.serialization.blocks.State;
}

test("build a CNN from the toolbox, diagnose shape and restore the saved graph", async () => {
  test.setTimeout(180000);
  const directory = await mkdtemp(path.join(tmpdir(), "easyai-toolbox-cnn-"));
  const projectDirectory = path.join(directory, "project");
  const stateDirectory = path.join(directory, "application-state");
  await mkdir(projectDirectory);
  await mkdir(stateDirectory);
  let app: ElectronApplication | undefined =
    await launchDesktop(stateDirectory);
  const failures: string[] = [];
  let failed = false;
  let shutdownUnconfirmed = false;
  try {
    expect(await app.evaluate(({ app }) => app.getPath("userData"))).toBe(
      stateDirectory,
    );
    expect(await app.evaluate(({ app }) => app.isPackaged)).toBe(
      Boolean(process.env.EASYAI_E2E_PACKAGE),
    );
    await observeTemporaryDesktop(app);
    await projectPicker(app, projectDirectory);
    const page = await app.firstWindow();
    page.setDefaultTimeout(8000);
    page.setDefaultNavigationTimeout(8000);
    page.on("pageerror", (error) => failures.push(error.name));
    page.on("console", (message) => {
      if (message.text().startsWith("EASYAI_TOOLBOX_SELECTION "))
        console.info(message.text());
      if (
        /Content Security Policy|Refused to (?:load|apply|execute|create)/i.test(
          message.text(),
        )
      )
        failures.push("CSP violation");
    });
    await page.evaluate(() => {
      let remaining = 64;
      const inspected = () =>
        document.querySelector('[aria-label="所选积木 ID"]')?.textContent ??
        null;
      const report = (kind: string, target: Element | null) => {
        if (remaining-- <= 0) return;
        console.info(
          "EASYAI_TOOLBOX_SELECTION",
          JSON.stringify({
            kind,
            targetTag: target?.tagName ?? null,
            targetBlock:
              target?.closest("g[data-id]")?.getAttribute("data-id") ?? null,
            activeTag: document.activeElement?.tagName ?? null,
            activeBlock:
              document.activeElement
                ?.closest("g[data-id]")
                ?.getAttribute("data-id") ?? null,
            inspected: inspected(),
          }),
        );
      };
      for (const kind of ["pointerdown", "focusin", "focusout"])
        document.addEventListener(
          kind,
          (event) =>
            report(kind, event.target instanceof Element ? event.target : null),
          true,
        );
      let previous = inspected();
      new MutationObserver(() => {
        const current = inspected();
        if (current !== previous) {
          previous = current;
          report("inspector", null);
        }
      }).observe(document.body, {
        childList: true,
        subtree: true,
        characterData: true,
      });
    });
    await expect(page.getByTestId("backend-status")).toHaveText(
      "本地服务已就绪。",
    );
    await page.getByRole("textbox", { name: "新工程名称" }).fill("Toolbox CNN");
    await page
      .getByRole("button", { name: "新建空白工程", exact: true })
      .click();
    await expect(
      page.getByRole("tab", { name: "数据处理", exact: true }),
    ).toBeVisible();
    const snapshot = async () =>
      JSON.parse(
        await readFile(
          path.join(projectDirectory, "project.easyai.json"),
          "utf8",
        ),
      ) as ProjectDocument;
    const blank = await snapshot();
    for (const workspace of Object.values(blank.workspaces))
      expect(workspace.blocks.blocks).toEqual([]);
    const data = new Canvas(page, "数据处理");
    const model = new Canvas(page, "模型结构");
    const training = new Canvas(page, "训练管线");
    const compile = page.getByRole("button", {
      name: "检查与编译",
      exact: true,
    });
    const saved = async () => {
      await expect(compile).toBeEnabled();
    };
    let preprocess = "",
      trainData = "",
      testData = "",
      trainLoader = "",
      testLoader = "";
    await test.step("drag and connect preprocessing, register datasets and choose stable references", async () => {
      preprocess = await interaction("data.drag 预处理流水线", () =>
        data.drag("预处理流水线", "数据处理", { row: 0 }),
      );
      await interaction("data.drag 转为张量", () =>
        data.drag("转为张量", "数据处理", {
          parent: preprocess,
          kind: "input",
        }),
      );
      await interaction("data.register preprocess Prep", () =>
        data.register(preprocess, "Prep"),
      );
      trainData = await interaction("data.drag 加载内置数据集", () =>
        data.drag("加载内置数据集", "数据处理", { row: 1 }),
      );
      await interaction("data.option trainData TRANSFORM_REF", () =>
        data.option(trainData, "TRANSFORM_REF", "Prep"),
      );
      await interaction("data.register trainData TrainData", () =>
        data.register(trainData, "TrainData"),
      );
      testData = await interaction("data.drag 加载内置数据集", () =>
        data.drag("加载内置数据集", "数据处理", { row: 2 }),
      );
      await interaction("data.option testData SPLIT", () =>
        data.option(testData, "SPLIT", "test"),
      );
      await interaction("data.option testData TRANSFORM_REF", () =>
        data.option(testData, "TRANSFORM_REF", "Prep"),
      );
      await interaction("data.register testData TestData", () =>
        data.register(testData, "TestData"),
      );
      trainLoader = await interaction("data.drag 创建 DataLoader", () =>
        data.drag("创建 DataLoader", "数据处理", { row: 3 }),
      );
      await interaction("data.option trainLoader DATASET_REF", () =>
        data.option(trainLoader, "DATASET_REF", "TrainData"),
      );
      await interaction("data.register trainLoader TrainBatches", () =>
        data.register(trainLoader, "TrainBatches"),
      );
      testLoader = await interaction("data.drag 创建 DataLoader", () =>
        data.drag("创建 DataLoader", "数据处理", { row: 4 }),
      );
      await interaction("data.option testLoader DATASET_REF", () =>
        data.option(testLoader, "DATASET_REF", "TestData"),
      );
      const shuffle = data.field(testLoader, "SHUFFLE");
      await interaction("data.checkbox testLoader SHUFFLE", () =>
        data.clickField(shuffle, "toggle test loader SHUFFLE"),
      );
      await interaction("data.register testLoader TestBatches", () =>
        data.register(testLoader, "TestBatches"),
      );
      await saved();
    });
    let definition = "",
      convolution = "",
      linear = "";
    await test.step("drag CNN layers into the model and connect their real notches", async () => {
      await page.getByRole("tab", { name: "模型结构", exact: true }).click();
      definition = await interaction("model.drag 定义模型类", () =>
        model.drag("定义模型类", "模型结构", { row: 0 }),
      );
      convolution = await interaction("model.drag 卷积层", () =>
        model.drag("卷积层", "模型结构", {
          parent: definition,
          kind: "input",
        }),
      );
      const relu = await interaction("model.drag ReLU", () =>
        model.drag("ReLU", "模型结构", {
          parent: convolution,
          kind: "next",
        }),
      );
      const pool = await interaction("model.drag 最大池化", () =>
        model.drag("最大池化", "模型结构", {
          parent: relu,
          kind: "next",
        }),
      );
      const flatten = await interaction("model.drag 展平", () =>
        model.drag("展平", "模型结构", {
          parent: pool,
          kind: "next",
        }),
      );
      linear = await interaction("model.drag 全连接层", () =>
        model.drag("全连接层", "模型结构", {
          parent: flatten,
          kind: "next",
        }),
      );
      await interaction("model.number linear IN_FEATURES", () =>
        model.number(linear, "IN_FEATURES", "3136"),
      );
      await interaction("model.number linear OUT_FEATURES", () =>
        model.number(linear, "OUT_FEATURES", "10"),
      );
      await interaction("model.register definition ToolboxCNN", () =>
        model.register(definition, "ToolboxCNN"),
      );
      await saved();
    });
    let loop = "";
    await test.step("choose the registered CNN and train/test loader references", async () => {
      await page.getByRole("tab", { name: "训练管线", exact: true }).click();
      loop = await interaction("training.drag 训练模型", () =>
        training.drag("训练模型", "训练管线", { row: 0 }),
      );
      await interaction("training.option loop MODEL_REF", () =>
        training.option(loop, "MODEL_REF", "ToolboxCNN"),
      );
      await interaction("training.option loop TRAIN_LOADER_REF", () =>
        training.option(loop, "TRAIN_LOADER_REF", "TrainBatches"),
      );
      await interaction("training.option loop TEST_LOADER_REF", () =>
        training.option(loop, "TEST_LOADER_REF", "TestBatches"),
      );
      await saved();
    });
    await compile.click();
    await expect(
      page.getByRole("status").filter({ hasText: /^代码检查通过/ }),
    ).toBeVisible();
    await page.getByText("查看当前工程的只读生成代码", { exact: true }).click();
    await expect(
      page.getByLabel("Monaco 只读代码视图").locator(".monaco-editor"),
    ).toBeVisible();
    const code = await page
      .locator(".code-view > ol > li code")
      .allTextContents();
    expect(code.join("\n")).toContain("class ToolboxCNN(nn.Module):");
    expect(code.join("\n")).toContain("nn.Conv2d(1, 16, 3, padding=1)");
    expect(code.join("\n")).toContain("nn.Linear(3136, 10)");
    await test.step("an actual layer edit reports the precise shape and its block, then repair it", async () => {
      await page.getByRole("tab", { name: "模型结构", exact: true }).click();
      await interaction("model.number linear IN_FEATURES", () =>
        model.number(linear, "IN_FEATURES", "3135"),
      );
      await saved();
      await compile.click();
      const mismatch = page
        .locator(".diagnostics li")
        .filter({ hasText: "SHAPE_MISMATCH" });
      await expect(mismatch).toHaveCount(1);
      await expect(mismatch).toContainText(
        "上一层输出为[3136]，当前层输入参数不匹配。",
      );
      await expect(mismatch.getByRole("button")).toHaveText(`源积木 ${linear}`);
      await expect(
        page.getByRole("button", { name: "开始本次运行", exact: true }),
      ).toBeDisabled();
      for (let repeat = 0; repeat < 2; repeat++) {
        await model.panSourceOut(linear, mismatch.getByRole("button"));
        await expect(
          page.getByLabel("所选积木 ID", { exact: true }),
        ).toHaveText(linear);
        await mismatch.getByRole("button").click();
        await model.sourceVisible(linear);
      }
      await expect(
        page
          .getByRole("complementary", { name: "对象注册与引用" })
          .getByLabel("所选积木 ID", { exact: true }),
      ).toHaveText(linear);
      await interaction("model.number linear IN_FEATURES", () =>
        model.number(linear, "IN_FEATURES", "3136"),
      );
      await saved();
      await compile.click();
      await expect(
        page.getByRole("status").filter({ hasText: /^代码检查通过/ }),
      ).toBeVisible();
      await expect
        .poll(() => page.locator(".code-view > ol > li code").allTextContents())
        .toEqual(code);
    });
    await test.step("repeat code-to-source navigation after panning the same selected block out", async () => {
      const expectedLine = code
        .find((line) => line.includes("nn.Linear(3136, 10)"))!
        .trim();
      const line = page
        .getByLabel("Monaco 只读代码视图")
        .locator(".monaco-editor .view-lines .view-line")
        .filter({ hasText: expectedLine });
      for (let repeat = 0; repeat < 2; repeat++) {
        await expect(line).toHaveCount(1);
        await model.panSourceOut(linear, line);
        await expect(
          page.getByLabel("所选积木 ID", { exact: true }),
        ).toHaveText(linear);
        await expect(line).toHaveCount(1);
        await line.click({ position: { x: 4, y: 4 } });
        await model.sourceVisible(linear);
        await expect(
          page.getByLabel("所选积木 ID", { exact: true }),
        ).toHaveText(linear);
      }
    });
    await saved();
    const built = await snapshot();
    // Verify actual saved IDs/references/connected CNN, not a test-injected graph.
    expect(built.projectId).toBe(blank.projectId);
    expect(built.workspaces.data.blocks.blocks).toHaveLength(5);
    const dataRoots = built.workspaces.data.blocks.blocks!.map(savedBlock);
    const root = (id: string) => dataRoots.find((block) => block.id === id)!;
    expect(root(preprocess).inputs?.steps?.block?.type).toBe("data.to_tensor");
    expect(root(trainData).fields?.TRANSFORM_REF).toBe(preprocess);
    expect(root(testData).fields?.TRANSFORM_REF).toBe(preprocess);
    expect(root(trainLoader).fields?.DATASET_REF).toBe(trainData);
    expect(root(testLoader).fields?.DATASET_REF).toBe(testData);
    expect(root(testLoader).fields?.SHUFFLE).toBe(false);
    const layers: string[] = [];
    let node = savedBlock(built.workspaces.model.blocks.blocks![0]).inputs?.body
      ?.block;
    while (node) {
      layers.push(node.type);
      node = node.next?.block;
    }
    expect(layers).toEqual([
      "model.conv2d",
      "model.relu",
      "model.maxpool2d",
      "model.flatten",
      "model.linear",
    ]);
    expect(built.workspaces.model.blocks.blocks![0].id).toBe(definition);
    const train = built.workspaces.training.blocks.blocks![0];
    expect(train.id).toBe(loop);
    expect(train.fields).toMatchObject({
      MODEL_REF: definition,
      TRAIN_LOADER_REF: trainLoader,
      TEST_LOADER_REF: testLoader,
    });
    expect(failures).toEqual([]);
    const previous = app;
    app = undefined;
    shutdownUnconfirmed = true;
    await interaction("normal saved desktop shutdown", () =>
      closeTemporaryDesktop(previous, false),
    );
    shutdownUnconfirmed = false;
    app = await launchDesktop(stateDirectory);
    await observeTemporaryDesktop(app);
    const reopened = await app.firstWindow();
    reopened.setDefaultTimeout(8000);
    reopened.setDefaultNavigationTimeout(8000);
    await expect(reopened.getByTestId("backend-status")).toHaveText(
      "本地服务已就绪。",
    );
    await expect(
      reopened.getByRole("tab", { name: "模型结构", exact: true }),
    ).toHaveAttribute("aria-selected", "true");
    await reopened
      .getByRole("button", { name: "检查与编译", exact: true })
      .click();
    await expect(
      reopened.getByRole("status").filter({ hasText: /^代码检查通过/ }),
    ).toBeVisible();
    await expect
      .poll(() =>
        reopened.locator(".code-view > ol > li code").allTextContents(),
      )
      .toEqual(code);
    expect((await snapshot()).workspaces).toEqual(built.workspaces);
    await expect(
      reopened.getByRole("button", { name: "开始本次运行", exact: true }),
    ).toBeDisabled();
  } catch (error) {
    failed = true;
    console.error(
      "EASYAI_TOOLBOX_RENDERER_FAILURES",
      JSON.stringify([...new Set(failures)]),
    );
    throw error;
  } finally {
    let closed = !app && !shutdownUnconfirmed;
    if (app) {
      try {
        await closeTemporaryDesktop(app, failed);
        closed = true;
      } catch (error) {
        console.error("EASYAI_TOOLBOX_CLOSE_FAILED");
        if (!failed) throw error;
        // Retain temporary files when shutdown was not confirmed.
      }
    }
    if (closed) {
      try {
        await rm(directory, { recursive: true });
      } catch (error) {
        console.error("EASYAI_TOOLBOX_TEMP_CLEANUP_FAILED");
        if (!failed) throw error;
      }
    }
  }
});
