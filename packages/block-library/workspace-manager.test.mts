import { describe, expect, it, vi } from "vitest";
import * as Blockly from "blockly/core";
import { readFileSync } from "node:fs";
import { createRequire } from "node:module";
import {
  WorkspaceManager,
  browserWorkspaceFactory,
  canonical,
  toolboxFor,
  validateWorkspaces,
  type WorkspaceFactory,
} from "../../apps/desktop/src/WorkspaceManager.js";
import type { ProjectDocument } from "../../apps/desktop/electron/bridge.js";
import { FieldSymbolRef } from "./symbols.mjs";

const settle = () => new Promise((resolve) => setTimeout(resolve, 20));
function fixture(): ProjectDocument {
  return JSON.parse(
    readFileSync(
      new URL("../contracts/fixtures/mnist.json", import.meta.url),
      "utf8",
    ),
  );
}
function setup(readOnly = false) {
  const callbacks = {
    onChange: vi.fn(),
    onSelect: vi.fn(),
    onTabChange: vi.fn(),
    onRefresh: vi.fn(),
  };
  const instances: Blockly.Workspace[] = [];
  const handles: {
    resize: ReturnType<typeof vi.fn>;
    dispose: ReturnType<typeof vi.fn>;
    setVisible: ReturnType<typeof vi.fn>;
    select: ReturnType<typeof vi.fn>;
  }[] = [];
  const factory: WorkspaceFactory = () => {
    const workspace = new Blockly.Workspace();
    instances.push(workspace);
    vi.spyOn(workspace, "addChangeListener");
    vi.spyOn(workspace, "removeChangeListener");
    const handle = {
      workspace,
      resize: vi.fn(),
      setVisible: vi.fn(),
      setReadOnly: vi.fn(),
      select: vi.fn(),
      dispose: vi.fn(() => workspace.dispose()),
    };
    handles.push(handle);
    return handle;
  };
  const hosts = {
    data: {} as HTMLElement,
    model: {} as HTMLElement,
    training: {} as HTMLElement,
  };
  const manager = new WorkspaceManager(hosts, readOnly, callbacks, factory);
  manager.receive(fixture().workspaces);
  return { manager, callbacks, instances, handles };
}

describe("persistent three-workspace lifecycle with real headless Blockly", () => {
  it("creates three handles/listeners once, and no save on load/tab/select/revision echo", async () => {
    const { manager, callbacks, instances, handles } = setup();
    try {
      const before = canonical(manager.serialize());
      manager.setActive("model");
      manager.setActive("data");
      manager.setActive("training");
      manager.receive(structuredClone(fixture().workspaces));
      const id = manager.workspaces.model.getTopBlocks(false)[0].id;
      manager.select(id);
      expect(callbacks.onTabChange).toHaveBeenCalledWith("model");
      await settle();
      expect(callbacks.onChange).not.toHaveBeenCalled();
      expect(canonical(manager.serialize())).toBe(before);
      expect(instances).toHaveLength(3);
      instances.forEach((workspace) =>
        expect(workspace.addChangeListener).toHaveBeenCalledTimes(1),
      );
      expect(handles[2].resize).toHaveBeenCalled();
    } finally {
      manager.dispose();
      manager.dispose();
      instances.forEach((workspace) =>
        expect(workspace.removeChangeListener).toHaveBeenCalledTimes(1),
      );
      handles.forEach((handle) =>
        expect(handle.dispose).toHaveBeenCalledTimes(1),
      );
    }
  });
  it("emits one actual field edit and preserves the canvas/ID when the parent echoes it", async () => {
    const { manager, callbacks, instances } = setup();
    try {
      const model = manager.workspaces.model.getTopBlocks(false)[0];
      manager.rename(model.id, "ChangedCNN");
      await settle();
      expect(callbacks.onChange).toHaveBeenCalledTimes(1);
      const saved = callbacks.onChange.mock.calls[0][0];
      manager.receive(saved);
      expect(manager.block(model.id)).toBe(model);
      expect(instances).toHaveLength(3);
    } finally {
      manager.dispose();
    }
  });
  it("refuses unknown/invalid imports before mutating live canvases or calling onChange", async () => {
    const { manager, callbacks } = setup();
    try {
      const original = canonical(manager.serialize());
      const changed = fixture().workspaces;
      changed.model.blocks.blocks![0].type = "future.layer";
      expect(() => manager.receive(changed)).toThrow("未知积木");
      expect(canonical(manager.serialize())).toBe(original);
      manager.rename(
        manager.workspaces.model.getTopBlocks(false)[0].id,
        "BlockedEdit",
      );
      await settle();
      expect(callbacks.onChange).not.toHaveBeenCalled();
      manager.receive(fixture().workspaces);
      manager.rename(
        manager.workspaces.model.getTopBlocks(false)[0].id,
        "RecoveredEdit",
      );
      await settle();
      expect(callbacks.onChange).toHaveBeenCalledTimes(1);
    } finally {
      manager.dispose();
    }
  });
  it("keeps unregister/delete Undo identity and makes new copied definitions unregistered", async () => {
    const { manager } = setup();
    try {
      const loader = manager.workspaces.data.getBlockById("train-loader")!;
      const field = loader.getField("DATASET_REF") as FieldSymbolRef;
      const dataset = manager.block(field.getValue()!)!;
      manager.setActive("data");
      manager.register(dataset.id, false);
      await settle();
      expect(field.status().valid).toBe(false);
      manager.undo();
      await settle();
      expect(field.status().valid).toBe(true);
      manager.remove(dataset.id);
      await settle();
      expect(field.status().valid).toBe(false);
      manager.undo();
      await settle();
      expect(field.status().valid).toBe(true);
      const restored = manager.block(dataset.id)!;
      const snapshot = Blockly.serialization.blocks.save(restored)!;
      snapshot.id = "copied-dataset";
      Blockly.serialization.blocks.append(snapshot, manager.workspaces.data, {
        recordUndo: true,
      });
      await settle();
      expect(
        manager.symbols().find((entry) => entry.id === "copied-dataset")
          ?.registered,
      ).toBe(false);
      expect(
        manager.symbols().find((entry) => entry.id === dataset.id)?.registered,
      ).toBe(true);
      manager.undo();
      await settle();
      expect(manager.block("copied-dataset")).toBeNull();
    } finally {
      manager.dispose();
    }
  });
  it("has all 21 manifest block types in the three toolboxes and rejects extra fields", () => {
    const types = ["data", "model", "training"].flatMap((tab) => {
      const toolbox = toolboxFor(tab as "data" | "model" | "training") as {
        contents: { contents: { type: string }[] }[];
      };
      return toolbox.contents.flatMap((category) =>
        category.contents.map((block) => block.type),
      );
    });
    expect(new Set(types).size).toBe(21);
    const value = fixture().workspaces;
    value.model.blocks.blocks![0].template = "untrusted.py";
    expect(() => validateWorkspaces(value)).toThrow("不支持的字段");
  });
  it("cleans handles already injected when a later factory call fails", () => {
    const disposed = vi.fn();
    let calls = 0;
    const factory: WorkspaceFactory = () => {
      if (++calls === 2) throw new Error("factory failed");
      const workspace = new Blockly.Workspace();
      return {
        workspace,
        resize: vi.fn(),
        select: vi.fn(),
        setReadOnly: vi.fn(),
        setVisible: vi.fn(),
        dispose: () => {
          disposed();
          workspace.dispose();
        },
      };
    };
    expect(
      () =>
        new WorkspaceManager(
          {
            data: {} as HTMLElement,
            model: {} as HTMLElement,
            training: {} as HTMLElement,
          },
          false,
          {
            onChange: vi.fn(),
            onSelect: vi.fn(),
            onTabChange: vi.fn(),
            onRefresh: vi.fn(),
          },
          factory,
        ),
    ).toThrow("factory failed");
    expect(disposed).toHaveBeenCalledTimes(1);
  });
  it("preserves native same-placement chains and rejects cross-placement connections", () => {
    const { manager } = setup();
    try {
      const workspace = manager.workspaces.model;
      const conv = workspace.newBlock("model.conv2d", "new-conv");
      const flatten = workspace.newBlock("model.flatten", "new-flatten");
      conv.nextConnection!.connect(flatten.previousConnection!);
      expect(conv.getNextBlock()).toBe(flatten);
      expect(() => validateWorkspaces(manager.serialize())).not.toThrow();
      const style = manager.workspaces.training.newBlock("viz.title");
      expect(
        conv
          .nextConnection!.getConnectionChecker()
          .canConnect(conv.nextConnection!, style.previousConnection!, false),
      ).toBe(false);
    } finally {
      manager.dispose();
    }
  });
  it("rejects overlong text edits and disables unsupported loss selections without replacing legacy values", () => {
    const { manager } = setup();
    try {
      const model = manager.workspaces.model.getTopBlocks(false)[0];
      const old = model.getFieldValue("NAME");
      model.setFieldValue("x".repeat(65), "NAME");
      expect(model.getFieldValue("NAME")).toBe(old);
      const field = manager.workspaces.training
        .getTopBlocks(false)[0]
        .getField("CRITERION") as Blockly.FieldDropdown & {
        onItemSelected_(menu: unknown, item: { getValue(): string }): void;
      };
      expect(
        field
          .getOptions(false)
          .map((option) => option[0])
          .join(" "),
      ).toContain("禁用");
      field.onItemSelected_(null, { getValue: () => "MSE" });
      expect(field.getValue()).toBe("CrossEntropy");
      field.loadState("MSE");
      expect(field.getValue()).toBe("MSE");
    } finally {
      manager.dispose();
    }
  });
});

it("initializes actual SVG canvases with local workspace accessibility messages", () => {
  const require = createRequire(import.meta.url);
  const { JSDOM } = require(
    require.resolve("jsdom", { paths: [require.resolve("blockly/core")] }),
  );
  const dom = new JSDOM("<!doctype html><html><body></body></html>");
  const handles: ReturnType<typeof browserWorkspaceFactory>[] = [];
  try {
    for (const key of [
      "window",
      "document",
      "Element",
      "HTMLElement",
      "Node",
      "SVGElement",
      "DOMParser",
      "XMLSerializer",
    ])
      vi.stubGlobal(
        key,
        key === "window"
          ? dom.window
          : key === "document"
            ? dom.window.document
            : dom.window[key],
      );
    for (const tab of ["data", "model", "training"] as const) {
      const host = document.createElement("div");
      document.body.append(host);
      const handle = browserWorkspaceFactory(host, tab, false);
      handles.push(handle);
      expect(handle.workspace).toBeInstanceOf(Blockly.WorkspaceSvg);
      const region = host.querySelector('[role="region"]');
      expect(region?.getAttribute("aria-label")).toContain("工作区");
      expect(
        host.querySelector('[role="figure"]')?.getAttribute("aria-label"),
      ).toContain("0");
    }
  } finally {
    handles.forEach((handle) => handle.dispose());
    dom.window.close();
    vi.unstubAllGlobals();
  }
});
