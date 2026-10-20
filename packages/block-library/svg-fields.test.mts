import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { createRequire } from "node:module";
import * as Blockly from "blockly/core";
import manifest from "./manifest.json";
import { registerBlocks } from "./register.mjs";
import {
  bindSymbolProvider,
  refreshReferences,
  setRegistration,
  symbolSnapshot,
} from "./symbols.mjs";
import { browserWorkspaceFactory } from "../../apps/desktop/src/WorkspaceManager.js";
import {
  fieldLabels,
  adjacentField,
  fieldLabelPattern,
  blockLabelPrefix,
} from "../../tests/e2e/canvas-fields.js";
const require = createRequire(import.meta.url);
const { JSDOM } = require(
  require.resolve("jsdom", { paths: [require.resolve("blockly/core")] }),
);
let dom: InstanceType<typeof JSDOM>;
let handle: ReturnType<typeof browserWorkspaceFactory> | undefined;
beforeEach(() => {
  registerBlocks();
  dom = new JSDOM("<!doctype html><html><body></body></html>", {
    pretendToBeVisual: true,
  });
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
  vi.stubGlobal(
    "requestAnimationFrame",
    dom.window.requestAnimationFrame.bind(dom.window),
  );
  vi.stubGlobal(
    "cancelAnimationFrame",
    dom.window.cancelAnimationFrame.bind(dom.window),
  );
  // JSDOM has no canvas/layout engine. Supply only controlled font metrics;
  // actual Blockly creates all fields, classes, SVG text and field order.
  vi.spyOn(
    dom.window.HTMLCanvasElement.prototype,
    "getContext",
  ).mockReturnValue({
    measureText: (text: string) => ({ width: text.length * 8 }),
  });
  const host = document.createElement("div");
  document.body.append(host);
  handle = browserWorkspaceFactory(host, "data", false);
});
afterEach(() => {
  handle?.dispose();
  handle = undefined;
  dom.window.close();
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
});
function control(root: Element, name: string) {
  const labels = [...root.querySelectorAll(fieldLabels)].filter((label) =>
    fieldLabelPattern(name).test(label.textContent ?? ""),
  );
  expect(labels, `unique actual static label ${name}`).toHaveLength(1);
  return document.evaluate(
    adjacentField.slice("xpath=".length),
    labels[0],
    null,
    dom.window.XPathResult.FIRST_ORDERED_NODE_TYPE,
    null,
  ).singleNodeValue;
}
it.each(manifest.blocks)(
  "maps the actual $id SVG header and every field to its real control",
  (spec) => {
    const block = handle!.workspace.newBlock(
      spec.id,
      `svg-${spec.id}`,
    ) as Blockly.BlockSvg;
    block.initSvg();
    for (const input of block.inputList)
      for (const field of input.fieldRow) field.getSize();
    const root = block.getSvgRoot();
    const header = root.querySelector(fieldLabels);
    expect(header?.textContent?.replace(/\u00a0/g, " ")).toBe(spec.label);
    expect(root.textContent).toMatch(blockLabelPrefix(spec.label));
    expect(header).toBe(block.inputList[0].fieldRow[0].getSvgRoot());
    for (const [name, fieldSpec] of Object.entries(spec.fields)) {
      const actual = control(root, name);
      expect(actual, `${spec.id}.${name}`).toBe(
        block.getField(name)!.getSvgRoot(),
      );
      expect((actual as Element).classList.contains("blocklyField")).toBe(true);
      if (fieldSpec.type === "boolean")
        expect(
          (actual as Element).classList.contains("blocklyCheckboxField"),
        ).toBe(true);
      else if (fieldSpec.type === "enum" || fieldSpec.type === "reference")
        expect(
          (actual as Element).classList.contains("blocklyDropdownField"),
        ).toBe(true);
      else if (fieldSpec.type === "integer" || fieldSpec.type === "number")
        expect(block.getField(name)).toBeInstanceOf(Blockly.FieldNumber);
      else expect(block.getField(name)).toBeInstanceOf(Blockly.FieldTextInput);
    }
  },
);

it("keeps real field identity after name, reference, number, enum and checkbox values change", () => {
  const workspace = handle!.workspace;
  const unbind = bindSymbolProvider(workspace, () =>
    symbolSnapshot({ data: workspace }),
  );
  try {
    const dataset = workspace.newBlock(
      "data.dataset_builtin",
      "svg-dataset",
    ) as Blockly.BlockSvg;
    const loader = workspace.newBlock(
      "data.dataloader",
      "svg-loader",
    ) as Blockly.BlockSvg;
    dataset.initSvg();
    loader.initSvg();
    const renderFields = () => {
      for (const block of [dataset, loader])
        for (const input of block.inputList)
          for (const field of input.fieldRow) field.getSize();
    };
    renderFields();
    const roots = new Map(
      ["NAME", "DATASET_REF", "BATCH_SIZE", "SHUFFLE"].map((name) => [
        name,
        control(loader.getSvgRoot(), name),
      ]),
    );
    // Unit-only model changes exercise real SVG rerendering and field identity;
    // the E2E still changes these exclusively through actual input/menus/clicks.
    loader.setFieldValue("NAME", "NAME");
    dataset.setFieldValue("TrainData", "NAME");
    setRegistration(dataset, true);
    loader.setFieldValue(dataset.id, "DATASET_REF");
    loader.setFieldValue(64, "BATCH_SIZE");
    loader.setFieldValue("FALSE", "SHUFFLE");
    dataset.setFieldValue("test", "SPLIT");
    refreshReferences({ data: workspace });
    renderFields();
    for (const [name, original] of roots) {
      expect(control(loader.getSvgRoot(), name)).toBe(original);
      expect(original).toBe(loader.getField(name)!.getSvgRoot());
    }
    expect(roots.get("NAME")?.textContent).toBe("NAME");
    expect(roots.get("DATASET_REF")?.textContent).toContain("TrainData");
    expect(roots.get("BATCH_SIZE")?.textContent).toBe("64");
    expect((roots.get("SHUFFLE") as Element).getAttribute("aria-checked")).toBe(
      "false",
    );
    expect(control(dataset.getSvgRoot(), "SPLIT")?.textContent).toContain(
      "test",
    );
    expect(loader.getFieldValue("DATASET_REF")).toBe(dataset.id);
    dataset.setFieldValue("RenamedData", "NAME");
    refreshReferences({ data: workspace });
    renderFields();
    expect(roots.get("DATASET_REF")?.textContent).toContain("RenamedData");
    expect(loader.getFieldValue("DATASET_REF")).toBe(dataset.id);
    expect(() => control(loader.getSvgRoot(), "missing")).toThrow(
      "unique actual static label missing",
    );
  } finally {
    unbind();
  }
});
