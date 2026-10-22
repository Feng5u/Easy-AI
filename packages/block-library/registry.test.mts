import { describe, it, expect } from "vitest";
import Blockly from "blockly/core";
import { registerBlocks } from "./register.mjs";
registerBlocks();

describe("real Blockly references and Undo", () => {
  it("preserves a missing reference ID and restores its definition on Undo", async () => {
    const ws = new Blockly.Workspace();
    try {
      const definition = ws.newBlock("data.dataset_builtin", "stable-dataset");
      const loader = ws.newBlock("data.dataloader", "loader");
      loader.setFieldValue(definition.id, "DATASET_REF");
      // Wait for Blockly's event queue before resetting the undo boundary.
      await new Promise<void>((resolve) => {
        const listener = (event: Blockly.Events.Abstract) => {
          if (event.type === Blockly.Events.BLOCK_CHANGE) {
            ws.removeChangeListener(listener);
            resolve();
          }
        };
        ws.addChangeListener(listener);
        definition.setFieldValue("TrainingData", "NAME");
      });
      ws.clearUndo();
      const deleted = new Promise<void>((resolve) => {
        const listener = (event: Blockly.Events.Abstract) => {
          if (event.type === Blockly.Events.BLOCK_DELETE) {
            ws.removeChangeListener(listener);
            resolve();
          }
        };
        ws.addChangeListener(listener);
      });
      definition.dispose(false);
      await deleted;
      expect(ws.getBlockById("stable-dataset")).toBeNull();
      expect(loader.getFieldValue("DATASET_REF")).toBe("stable-dataset");
      ws.undo(false);
      expect(ws.getBlockById("stable-dataset")?.getFieldValue("NAME")).toBe(
        "TrainingData",
      );
      expect(loader.getFieldValue("DATASET_REF")).toBe("stable-dataset");
    } finally {
      ws.dispose();
    }
  });
});
