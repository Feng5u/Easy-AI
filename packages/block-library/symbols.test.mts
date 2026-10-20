import { afterEach, describe, expect, it } from "vitest";
import * as Blockly from "blockly/core";
import { readFileSync } from "node:fs";
import { registerBlocks } from "./register.mjs";
import {
  bindSymbolProvider,
  FieldSymbolRef,
  refreshReferences,
  setRegistration,
  symbolSnapshot,
} from "./symbols.mjs";

registerBlocks();
const opened: Blockly.Workspace[] = [];
const settle = () => new Promise((resolve) => setTimeout(resolve, 15));
function project() {
  const value = JSON.parse(
    readFileSync(
      new URL("../contracts/fixtures/mnist.json", import.meta.url),
      "utf8",
    ),
  );
  const workspaces = Object.fromEntries(
    ["data", "model", "training"].map((tab) => {
      const workspace = new Blockly.Workspace();
      opened.push(workspace);
      Blockly.Events.disable();
      try {
        Blockly.serialization.workspaces.load(value.workspaces[tab], workspace);
      } finally {
        Blockly.Events.enable();
      }
      return [tab, workspace];
    }),
  ) as Record<"data" | "model" | "training", Blockly.Workspace>;
  for (const workspace of Object.values(workspaces))
    bindSymbolProvider(workspace, () => symbolSnapshot(workspaces));
  return workspaces;
}
afterEach(() => {
  opened.splice(0).forEach((workspace) => workspace.dispose());
});
describe("real Blockly stable references", () => {
  it("indexes role definitions and retains IDs on rename across pages", () => {
    const workspaces = project();
    const loop =
      workspaces.training.getBlockById("training-root") ??
      workspaces.training.getTopBlocks(false)[0];
    const field = loop.getField("MODEL_REF") as FieldSymbolRef;
    expect(field).toBeInstanceOf(FieldSymbolRef);
    const id = field.getValue()!;
    workspaces.model.getBlockById(id)!.setFieldValue("RenamedCNN", "NAME");
    refreshReferences(workspaces);
    expect(field.getValue()).toBe(id);
    expect(field.getText()).toBe("RenamedCNN");
    expect(symbolSnapshot(workspaces)).toHaveLength(6);
  });
  it("filters train/test choices and keeps an invalid prior choice as a warning tombstone", () => {
    const workspaces = project();
    const loop = workspaces.training.getTopBlocks(false)[0];
    const field = loop.getField("TRAIN_LOADER_REF") as FieldSymbolRef;
    expect(
      field
        .getOptions(false)
        .some(
          ([label, id]) =>
            id === "test-loader" && !String(label).startsWith("⚠"),
        ),
    ).toBe(false);
    field.setValue("test-loader");
    expect(field.getValue()).toBe("test-loader");
    expect(field.status().valid).toBe(false);
    expect(field.getText()).toContain("角色不符");
    const loader = workspaces.data.getBlockById("test-loader")!;
    const dataset = workspaces.data.getBlockById(
      loader.getFieldValue("DATASET_REF"),
    )!;
    dataset.setFieldValue("train", "SPLIT");
    expect(field.status().valid).toBe(true);
  });
  it("unregister mutation and actual Undo restore references, without resetting their value", async () => {
    const workspaces = project();
    const loop = workspaces.training.getTopBlocks(false)[0];
    const field = loop.getField("TRAIN_LOADER_REF") as FieldSymbolRef;
    const id = field.getValue()!;
    workspaces.data.clearUndo();
    setRegistration(workspaces.data.getBlockById(id)!, false);
    await settle();
    expect(field.status().valid).toBe(false);
    expect(field.getValue()).toBe(id);
    workspaces.data.undo(false);
    await settle();
    expect(field.status().valid).toBe(true);
    expect(field.getValue()).toBe(id);
  });
  it("deletion and actual Undo preserve the old symbol identity", async () => {
    const workspaces = project();
    const loader = workspaces.data.getBlockById("train-loader")!;
    const field = loader.getField("DATASET_REF") as FieldSymbolRef;
    const id = field.getValue()!;
    workspaces.data.getBlockById(id)!.dispose(false);
    await settle();
    expect(field.status().valid).toBe(false);
    expect(field.getValue()).toBe(id);
    expect(field.getText()).toContain("已删除");
    workspaces.data.undo(false);
    await settle();
    expect(field.status().valid).toBe(true);
    expect(field.getValue()).toBe(id);
  });
  it("loads a missing field ID without ordinary dropdown fallback", () => {
    const workspaces = project();
    const loop = workspaces.training.getTopBlocks(false)[0];
    const field = loop.getField("MODEL_REF") as FieldSymbolRef;
    field.loadState("missing-original-id");
    expect(field.getValue()).toBe("missing-original-id");
    expect(field.getOptions(false).at(-1)?.[1]).toBe("missing-original-id");
    const snapshot = Blockly.serialization.workspaces.save(workspaces.training);
    expect(snapshot.blocks.blocks[0].fields.MODEL_REF).toBe(
      "missing-original-id",
    );
  });
});
