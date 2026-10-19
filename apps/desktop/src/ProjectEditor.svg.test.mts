import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { act, createElement, useState } from "react";
import type { Root } from "react-dom/client";
import { createRequire } from "node:module";
import * as Blockly from "blockly/core";
import type { ProjectDocument } from "../electron/bridge.js";
import type { ManagerCallbacks } from "./WorkspaceManager.js";
import { WorkspaceManager } from "./WorkspaceManager.js";
import { ProjectEditor } from "./ProjectEditor.js";
const captured = vi.hoisted(() => ({ managers: [] as WorkspaceManager[] }));
vi.mock("./WorkspaceManager.js", async (original) => {
  const actual = await original<typeof import("./WorkspaceManager.js")>();
  return {
    ...actual,
    WorkspaceManager: class extends actual.WorkspaceManager {
      constructor(
        hosts: Record<"data" | "model" | "training", HTMLElement>,
        readOnly: boolean,
        callbacks: ManagerCallbacks,
      ) {
        super(hosts, readOnly, callbacks);
        captured.managers.push(this);
      }
    },
  };
});
const require = createRequire(import.meta.url);
const { JSDOM } = require(
  require.resolve("jsdom", { paths: [require.resolve("blockly/core")] }),
);
let dom: InstanceType<typeof JSDOM>,
  container: HTMLDivElement,
  root: Root | undefined;
beforeEach(() => {
  captured.managers.length = 0;
  dom = new JSDOM("<!doctype html><html><body></body></html>", {
    pretendToBeVisual: true,
    url: "http://localhost",
  });
  for (const key of [
    "window",
    "document",
    "navigator",
    "Element",
    "HTMLElement",
    "Node",
    "SVGElement",
    "FocusEvent",
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
  vi.stubGlobal("IS_REACT_ACT_ENVIRONMENT", true);
  vi.stubGlobal(
    "requestAnimationFrame",
    dom.window.requestAnimationFrame.bind(dom.window),
  );
  vi.stubGlobal(
    "cancelAnimationFrame",
    dom.window.cancelAnimationFrame.bind(dom.window),
  );
  // Controlled font/field rectangles compensate only for JSDOM's missing
  // layout. Production Blockly creates and destroys the actual HTML editor.
  vi.spyOn(
    dom.window.HTMLCanvasElement.prototype,
    "getContext",
  ).mockReturnValue({
    measureText: (text: string) => ({ width: text.length * 8 }),
  });
  vi.spyOn(Blockly.Field.prototype, "getScaledBBox").mockReturnValue(
    new Blockly.utils.Rect(0, 24, 0, 100),
  );
  container = document.createElement("div");
  document.body.append(container);
});
afterEach(async () => {
  Blockly.WidgetDiv.hide();
  if (root) await act(async () => root!.unmount());
  root = undefined;
  // Drain the real queue before closing this window: JSDOM cancels its pending
  // rAF callbacks on close, including Blockly's event-dispatch scheduling.
  const barrier = new Blockly.Workspace();
  await new Promise<void>((resolve) => {
    barrier.addChangeListener(() => resolve());
    Blockly.Events.fire(
      new Blockly.Events.Click(
        null,
        barrier.id,
        Blockly.Events.ClickTarget.ZOOM_CONTROLS,
      ),
    );
  });
  barrier.dispose();
  dom.window.close();
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
});
async function mount() {
  const onSelect = vi.fn();
  const onChange = vi.fn();
  function Screen() {
    const [project, setProject] = useState<ProjectDocument>({
      projectId: "2c92b153-77e4-4bb4-874e-adcc8b2a6e36",
      name: "SVG input lifecycle",
      revision: 1,
      workspaces: {
        data: { blocks: { blocks: [] } },
        model: { blocks: { blocks: [] } },
        training: { blocks: { blocks: [] } },
      },
      ui: { activeTab: "model", codeVisible: false },
      settings: { executionMode: "full" },
    });
    const [selected, setSelected] = useState<string | null>(null);
    const [tab, setTab] = useState<"data" | "model" | "training">("model");
    return createElement(ProjectEditor, {
      project,
      readOnly: false,
      selectedBlock: selected,
      activeTab: tab,
      onSelect(id) {
        onSelect(id);
        setSelected(id);
      },
      onTabChange: setTab,
      onChange(workspaces) {
        onChange(workspaces);
        setProject((old) => ({ ...old, workspaces }));
      },
    });
  }
  const { createRoot } = await import("react-dom/client");
  root = createRoot(container);
  await act(async () => root!.render(createElement(Screen)));
  return { manager: captured.managers[0], onSelect, onChange };
}
function initialize(block: Blockly.BlockSvg) {
  block.initSvg();
  for (const input of block.inputList)
    for (const field of input.fieldRow) field.getSize();
}
it("keeps a reopened actual number editor alive through the native selection echo", async () => {
  const { manager, onSelect, onChange } = await mount();
  const workspace = manager.workspaces.model as Blockly.WorkspaceSvg;
  let block!: Blockly.BlockSvg;
  await act(async () => {
    block = workspace.newBlock(
      "model.linear",
      "svg-reopened-linear",
    ) as Blockly.BlockSvg;
    initialize(block);
    await vi.waitFor(() => expect(onChange).toHaveBeenCalled());
  });
  const field = block.getField("IN_FEATURES") as Blockly.FieldNumber;
  // Finish a first edit on an already selected block, then select the training
  // block and return, matching the failing second edit rather than claiming
  // that number inputs never worked.
  await act(async () => {
    Blockly.getFocusManager().focusNode(block);
    await vi.waitFor(() => expect(onSelect).toHaveBeenLastCalledWith(block.id));
  });
  onChange.mockClear();
  await act(async () => {
    field.showEditor();
    const first = document.querySelector<HTMLInputElement>(
      "input.blocklyHtmlInput",
    )!;
    first.value = "3136";
    first.dispatchEvent(new dom.window.Event("input", { bubbles: true }));
    first.dispatchEvent(
      new dom.window.KeyboardEvent("keydown", { key: "Enter", bubbles: true }),
    );
    await vi.waitFor(() => expect(onChange).toHaveBeenCalled());
  });
  expect(field.getValue()).toBe(3136);
  onChange.mockClear();
  await act(async () => {
    block.getField("OUT_FEATURES")!.showEditor();
    const output = document.querySelector<HTMLInputElement>(
      "input.blocklyHtmlInput",
    )!;
    output.value = "10";
    output.dispatchEvent(new dom.window.Event("input", { bubbles: true }));
    output.dispatchEvent(
      new dom.window.KeyboardEvent("keydown", { key: "Enter", bubbles: true }),
    );
    await vi.waitFor(() => expect(onChange).toHaveBeenCalled());
  });
  expect(block.getFieldValue("OUT_FEATURES")).toBe(10);
  let loop!: Blockly.BlockSvg;
  await act(async () => {
    const trainingTab = container.querySelector<HTMLButtonElement>(
      '[role="tab"][aria-controls$="-training"]',
    )!;
    trainingTab.click();
  });
  await act(async () => {
    loop = manager.workspaces.training.newBlock(
      "train.loop",
      "svg-selected-training",
    ) as Blockly.BlockSvg;
    initialize(loop);
    Blockly.getFocusManager().focusNode(loop);
    await vi.waitFor(() => expect(onSelect).toHaveBeenLastCalledWith(loop.id));
  });
  await act(async () => {
    container
      .querySelector<HTMLButtonElement>(
        '[role="tab"][aria-controls$="-model"]',
      )!
      .click();
  });
  const center = vi.spyOn(workspace, "centerOnBlock");
  let input!: HTMLInputElement;
  await act(async () => {
    // Unit-only public focus/editor APIs reproduce the native Blockly lifecycle.
    // No field value setter, fake HTML input or fake selection event is used.
    Blockly.getFocusManager().focusNode(block);
    field.showEditor();
    input = document.querySelector<HTMLInputElement>("input.blocklyHtmlInput")!;
    expect(input).not.toBeNull();
    expect(input.isConnected).toBe(true);
    await vi.waitFor(() => expect(onSelect).toHaveBeenLastCalledWith(block.id));
  });
  expect(input.isConnected).toBe(true);
  expect(center).not.toHaveBeenCalled();
  expect(document.activeElement).toBe(input);
  onChange.mockClear();
  await act(async () => {
    input.value = "3135";
    input.dispatchEvent(new dom.window.Event("input", { bubbles: true }));
    await vi.waitFor(() => expect(onChange).toHaveBeenCalled());
  });
  // Intermediate field events also pass through real serialize/props receive
  // while this exact editor remains open. Enter closes it only when requested.
  expect(field.getValue()).toBe(3135);
  expect(input.isConnected).toBe(true);
  expect(document.activeElement).toBe(input);
  const committed = new Promise<void>((resolve) => {
    const listener = (event: Blockly.Events.Abstract) => {
      if (
        event.type === Blockly.Events.BLOCK_CHANGE &&
        (event as Blockly.Events.BlockChange).blockId === block.id &&
        (event as Blockly.Events.BlockChange).name === "IN_FEATURES"
      ) {
        workspace.removeChangeListener(listener);
        resolve();
      }
    };
    workspace.addChangeListener(listener);
  });
  await act(async () => {
    input.dispatchEvent(
      new dom.window.KeyboardEvent("keydown", { key: "Enter", bubbles: true }),
    );
    await committed;
  });
  expect(field.getValue()).toBe(3135);
  expect(input.isConnected).toBe(false);
  expect(manager.block(block.id)).toBe(block);
  onChange.mockClear();
  await act(async () => {
    field.showEditor();
    const repair = document.querySelector<HTMLInputElement>(
      "input.blocklyHtmlInput",
    )!;
    repair.value = "3136";
    repair.dispatchEvent(new dom.window.Event("input", { bubbles: true }));
    repair.dispatchEvent(
      new dom.window.KeyboardEvent("keydown", { key: "Enter", bubbles: true }),
    );
    await vi.waitFor(() => expect(onChange).toHaveBeenCalled());
  });
  expect(field.getValue()).toBe(3136);
  expect(onChange.mock.lastCall![0]).toEqual(manager.serialize());
  expect(manager.block(block.id)).toBe(block);
  act(() => manager.select(block.id));
  expect(center).toHaveBeenCalledWith(block.id);
});

it("keeps the actual reference menu alive through native selection and commits the chosen stable ID", async () => {
  const { manager, onSelect, onChange } = await mount();
  const workspace = manager.workspaces.data as Blockly.WorkspaceSvg;
  let prep!: Blockly.BlockSvg, dataset!: Blockly.BlockSvg;
  await act(async () => {
    container
      .querySelector<HTMLButtonElement>('[role="tab"][aria-controls$="-data"]')!
      .click();
  });
  await act(async () => {
    prep = workspace.newBlock(
      "data.compose",
      "svg-reference-prep",
    ) as Blockly.BlockSvg;
    dataset = workspace.newBlock(
      "data.dataset_builtin",
      "svg-reference-dataset",
    ) as Blockly.BlockSvg;
    initialize(prep);
    initialize(dataset);
    await vi.waitFor(() => expect(onChange).toHaveBeenCalled());
  });
  // Unit fixture setup uses the actual registration checks and event pipeline.
  onChange.mockClear();
  await act(async () => {
    manager.rename(prep.id, "Prep");
    manager.register(prep.id, true);
    await vi.waitFor(() => expect(onChange).toHaveBeenCalled());
  });
  const field = dataset.getField("TRANSFORM_REF") as Blockly.FieldDropdown;
  const center = vi.spyOn(workspace, "centerOnBlock");
  let menu!: HTMLElement;
  await act(async () => {
    Blockly.getFocusManager().focusNode(dataset);
    field.showEditor();
    menu = document.querySelector<HTMLElement>(
      '[role="listbox"].blocklyDropdownMenu',
    )!;
    expect(menu).not.toBeNull();
    await vi.waitFor(() =>
      expect(onSelect).toHaveBeenLastCalledWith(dataset.id),
    );
  });
  expect(menu.isConnected).toBe(true);
  expect(center).not.toHaveBeenCalled();
  expect(field.getSvgRoot()!.getAttribute("aria-expanded")).toBe("true");
  const option = [
    ...menu.querySelectorAll<HTMLElement>('[role="option"]'),
  ].find((node) => node.getAttribute("aria-label") === "Prep")!;
  expect(option).not.toBeUndefined();
  onChange.mockClear();
  await act(async () => {
    option.dispatchEvent(
      new dom.window.PointerEvent("pointerup", {
        bubbles: true,
        pointerId: 1,
        pointerType: "mouse",
        isPrimary: true,
        button: 0,
        clientX: 5,
        clientY: 5,
      }),
    );
    await vi.waitFor(() => expect(onChange).toHaveBeenCalled());
  });
  expect(field.getValue()).toBe(prep.id);
  expect(field.getSvgRoot()!.getAttribute("aria-expanded")).toBe("false");
  expect(onChange.mock.lastCall![0]).toEqual(manager.serialize());
  expect(manager.block(dataset.id)).toBe(dataset);
});
