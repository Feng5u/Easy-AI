import { it, expect } from "vitest";
import Blockly from "blockly/core";
import { mkdtemp, mkdir, readFile, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { fileURLToPath } from "node:url";
import { registerBlocks } from "../../../packages/block-library/register.mjs";
import {
  bindSymbolProvider,
  symbolSnapshot,
  setRegistration,
  FieldSymbolRef,
} from "../../../packages/block-library/symbols.mjs";
import { startBackend } from "./backend.mjs";
import { MainWorkflow } from "./workflow.mjs";
import type {
  CompileResult,
  ProjectDocument,
  ProjectSession,
  SelectionResult,
} from "./bridge.js";

it("builds a new editable program from empty Blockly workspaces through real save/compile/import/export APIs", async () => {
  registerBlocks();
  const root = await mkdtemp(join(tmpdir(), "easyai-editor-"));
  const projectRoot = join(root, "新建 空白工程");
  const importedRoot = join(root, "导入 空白目标");
  await mkdir(projectRoot);
  await mkdir(importedRoot);
  const cwd = fileURLToPath(
    new URL("../../../services/backend/", import.meta.url),
  );
  const backend = await startBackend(
    join(
      cwd,
      process.platform === "win32"
        ? ".venv/Scripts/python.exe"
        : ".venv/bin/python",
    ),
    cwd,
    10000,
    join(root, "state"),
  );
  const exportPath = join(root, "portable.easyai.json");
  const workflow = new MainWorkflow(
    () => backend,
    async () => projectRoot,
    () => undefined,
    {
      importProject: async () => ({
        sourcePath: exportPath,
        destinationPath: importedRoot,
      }),
      exportProject: async () => exportPath,
    },
  );
  const workspaces = {
    data: new Blockly.Workspace(),
    model: new Blockly.Workspace(),
    training: new Blockly.Workspace(),
  };
  const unbind = Object.values(workspaces).map((ws) =>
    bindSymbolProvider(ws, () => symbolSnapshot(workspaces)),
  );
  try {
    const selected = (await workflow.invoke("easyai:selections:pick", [
      "project",
    ])) as SelectionResult;
    const blank = (await workflow.invoke("easyai:projects:create", [
      selected.selectionId,
      "华为 ICT 实验",
      "blank",
    ])) as ProjectSession;
    if (!blank.project) throw new Error("Expected blank editable project");
    expect(blank.project.workspaces.data.blocks.blocks).toEqual([]);
    function add(
      tab: keyof typeof workspaces,
      type: string,
      id: string,
      fields: Record<string, string> = {},
    ) {
      const block = workspaces[tab].newBlock(type, id);
      for (const [name, value] of Object.entries(fields))
        block.setFieldValue(value, name);
      return block;
    }
    const transform = add("data", "data.compose", "ui-transform", {
      NAME: "preprocess",
    });
    const tensor = add("data", "data.to_tensor", "ui-tensor");
    transform
      .getInput("steps")!
      .connection!.connect(tensor.previousConnection!);
    setRegistration(transform, true);
    for (const split of ["train", "test"]) {
      const dataset = add(
        "data",
        "data.dataset_builtin",
        `ui-dataset-${split}`,
        {
          NAME: split === "train" ? "LearningData" : "EvaluationData",
          SPLIT: split,
          TRANSFORM_REF: transform.id,
        },
      );
      setRegistration(dataset, true);
      const loader = add("data", "data.dataloader", `ui-loader-${split}`, {
        NAME: split === "train" ? "LearningBatches" : "EvaluationBatches",
        DATASET_REF: dataset.id,
        SHUFFLE: split === "train" ? "TRUE" : "FALSE",
      });
      setRegistration(loader, true);
    }
    const model = add("model", "model.define", "ui-network", {
      NAME: "ICTNetwork",
    });
    const flatten = add("model", "model.flatten", "ui-flatten");
    const linear = add("model", "model.linear", "ui-linear", {
      IN_FEATURES: "784",
      OUT_FEATURES: "10",
    });
    model.getInput("body")!.connection!.connect(flatten.previousConnection!);
    flatten.nextConnection!.connect(linear.previousConnection!);
    setRegistration(model, true);
    const training = add("training", "train.loop", "ui-training", {
      MODEL_REF: model.id,
      TRAIN_LOADER_REF: "ui-loader-train",
      TEST_LOADER_REF: "ui-loader-test",
      EPOCHS: "1",
    });
    const trainRef = training.getField("TRAIN_LOADER_REF") as FieldSymbolRef;
    expect(trainRef.referenceOptions().map((item) => item[1])).toContain(
      "ui-loader-train",
    );
    expect(trainRef.referenceOptions().map((item) => item[1])).not.toContain(
      "ui-loader-test",
    );
    const serialize = () =>
      Object.fromEntries(
        Object.entries(workspaces).map(([tab, ws]) => [
          tab,
          Blockly.serialization.workspaces.save(ws),
        ]),
      ) as unknown as ProjectDocument["workspaces"];
    let saved = (await workflow.invoke("easyai:projects:save", [
      { ...blank.project, workspaces: serialize() },
      1,
    ])) as ProjectSession;
    if (!saved.project) throw new Error("Expected saved program");
    let compiled = (await workflow.invoke("easyai:projects:compile", [
      saved.project,
      1,
    ])) as CompileResult;
    expect(compiled.runnable, JSON.stringify(compiled.diagnostics)).toBe(true);
    expect(compiled.code).toContain("nn.Linear(784, 10)");
    expect(compiled.code).toContain("loss.backward()");
    expect(
      compiled.sourceMap?.some((span) => span.origin.blockId === "ui-linear"),
    ).toBe(true);
    linear.setFieldValue("20", "OUT_FEATURES");
    const output = add("model", "model.linear", "ui-added-output", {
      IN_FEATURES: "20",
      OUT_FEATURES: "10",
    });
    linear.nextConnection!.connect(output.previousConnection!);
    saved = (await workflow.invoke("easyai:projects:save", [
      { ...saved.project, workspaces: serialize() },
      2,
    ])) as ProjectSession;
    if (!saved.project) throw new Error("Expected edited program");
    compiled = (await workflow.invoke("easyai:projects:compile", [
      saved.project,
      2,
    ])) as CompileResult;
    expect(compiled.runnable).toBe(true);
    expect(compiled.code).toContain("nn.Linear(784, 20)");
    expect(compiled.code).toContain("nn.Linear(20, 10)");
    expect(
      compiled.sourceMap?.some((span) => span.origin.blockId === output.id),
    ).toBe(true);
    expect(
      await workflow.invoke("easyai:runs:list", [
        saved.project.projectId,
        0,
        25,
      ]),
    ).toEqual([]);
    expect(await workflow.invoke("easyai:projects:export", [])).toEqual({
      exported: true,
    });
    expect(await readFile(exportPath)).toEqual(
      await readFile(join(projectRoot, "project.easyai.json")),
    );
    const imported = (await workflow.invoke(
      "easyai:projects:import",
      [],
    )) as ProjectSession;
    expect(imported.project?.projectId).not.toBe(saved.project.projectId);
    expect(imported.project?.workspaces).toEqual(saved.project.workspaces);
  } finally {
    for (const release of unbind) release();
    for (const ws of Object.values(workspaces)) ws.dispose();
    workflow.dispose();
    await backend.stop();
    await rm(root, { recursive: true, force: true });
  }
}, 20000);
