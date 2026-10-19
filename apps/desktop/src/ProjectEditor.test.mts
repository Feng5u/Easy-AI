import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { act, createElement, useState } from "react";
import type { Root } from "react-dom/client";
import { createRequire } from "node:module";
import { readFileSync } from "node:fs";
import type { ProjectDocument } from "../electron/bridge.js";
import type { ManagerCallbacks, WorkspaceFactory } from "./WorkspaceManager.js";
import { WorkspaceManager } from "./WorkspaceManager.js";
import { ProjectEditor } from "./ProjectEditor.js";
const captured = vi.hoisted(() => ({ managers: [] as WorkspaceManager[] }));
vi.mock("./WorkspaceManager.js", async (original) => {
  const actual = await original<typeof import("./WorkspaceManager.js")>();
  const Blockly = await import("blockly/core");
  return {
    ...actual,
    WorkspaceManager: class extends actual.WorkspaceManager {
      constructor(
        hosts: Record<"data" | "model" | "training", HTMLElement>,
        readOnly: boolean,
        callbacks: ManagerCallbacks,
      ) {
        // Only replace the pixel renderer. Registration, fields, event queues,
        // symbol snapshots and serialization are the production implementation.
        const factory: WorkspaceFactory = () => {
          const workspace = new Blockly.Workspace();
          return {
            workspace,
            resize() {},
            setVisible() {},
            setReadOnly() {},
            select() {},
            dispose: () => workspace.dispose(),
          };
        };
        super(hosts, readOnly, callbacks, factory);
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
    url: "http://localhost",
  });
  for (const [key, value] of Object.entries({
    window: dom.window,
    document: dom.window.document,
    navigator: dom.window.navigator,
    HTMLElement: dom.window.HTMLElement,
    IS_REACT_ACT_ENVIRONMENT: true,
  }))
    vi.stubGlobal(key, value);
  container = document.createElement("div");
  document.body.append(container);
});
afterEach(async () => {
  if (root) await act(async () => root!.unmount());
  root = undefined;
  dom.window.close();
  vi.unstubAllGlobals();
});
function fixture(): ProjectDocument {
  const project: ProjectDocument = JSON.parse(
    readFileSync(
      new URL(
        "../../../packages/contracts/fixtures/mnist.json",
        import.meta.url,
      ),
      "utf8",
    ),
  );
  for (const tab of ["data", "model"] as const)
    for (const block of project.workspaces[tab].blocks.blocks ?? [])
      block.extraState = { easyai: { version: 1, registered: false } };
  return project;
}
async function mount(id: string, readOnly = false, initial = fixture()) {
  const onChange = vi.fn();
  function Screen() {
    const [project, setProject] = useState(initial);
    const [selected, setSelected] = useState<string | null>(id);
    const [tab, setTab] = useState<"data" | "model" | "training">(
      id === "cnn" ? "model" : "data",
    );
    return createElement(ProjectEditor, {
      project,
      readOnly,
      selectedBlock: selected,
      activeTab: tab,
      onSelect: setSelected,
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
  return { manager: captured.managers[0], onChange };
}
it.each([
  "transform",
  "train-dataset",
  "test-dataset",
  "train-loader",
  "test-loader",
  "cnn",
])(
  "commits checkbox state before queued Blockly events for %s and preserves the saved ID",
  async (id) => {
    const { manager, onChange } = await mount(id);
    const checkbox = container.querySelector<HTMLInputElement>(
      'input[type="checkbox"]',
    )!;
    expect(checkbox.checked).toBe(false);
    // Real DOM activation and React controlled-input restoration, with no timer
    // or synthetic change event. Blockly's queued notification is still pending.
    act(() => checkbox.click());
    expect(
      manager.symbols().find((symbol) => symbol.id === id)?.registered,
    ).toBe(true);
    expect(checkbox.checked).toBe(true);
    expect(
      container.querySelector('[aria-label="所选积木 ID"]')?.textContent,
    ).toBe(id);
    await act(async () => {
      await vi.waitFor(() => expect(onChange).toHaveBeenCalled());
    });
    expect(checkbox.checked).toBe(true);
    expect(manager.block(id)?.saveExtraState?.()).toEqual({
      easyai: { version: 1, registered: true },
    });
    const latest = onChange.mock.lastCall![0];
    expect(latest).toEqual(manager.serialize());
    onChange.mockClear();
    act(() => checkbox.click());
    expect(checkbox.checked).toBe(false);
    await act(async () => {
      await vi.waitFor(() => expect(onChange).toHaveBeenCalled());
    });
    expect(manager.block(id)?.saveExtraState?.()).toEqual({
      easyai: { version: 1, registered: false },
    });
  },
);

it("commits rename then registration without a timer and keeps reference identity across Undo and Redo", async () => {
  const { manager, onChange } = await mount("transform");
  const input = container.querySelector<HTMLInputElement>(
    'input:not([type="checkbox"])',
  )!;
  const checkbox = container.querySelector<HTMLInputElement>(
    'input[type="checkbox"]',
  )!;
  const reference = () =>
    manager.block("train-dataset")!.getFieldValue("TRANSFORM_REF");
  expect(reference()).toBe("transform");
  act(() => {
    input.focus();
    Object.getOwnPropertyDescriptor(
      dom.window.HTMLInputElement.prototype,
      "value",
    )!.set!.call(input, "Prep");
    input.dispatchEvent(new dom.window.Event("input", { bubbles: true }));
  });
  act(() => {
    input.dispatchEvent(
      new dom.window.KeyboardEvent("keydown", { key: "Enter", bubbles: true }),
    );
  });
  expect(manager.block("transform")!.getFieldValue("NAME")).toBe("Prep");
  expect(input.value).toBe("Prep");
  act(() => checkbox.click());
  expect(checkbox.checked).toBe(true);
  expect(reference()).toBe("transform");
  await act(async () => {
    await vi.waitFor(() => expect(onChange).toHaveBeenCalled());
  });
  const history = async (label: string) => {
    onChange.mockClear();
    await act(async () => {
      const button = [...container.querySelectorAll("button")].find(
        (node) => node.textContent === label,
      )!;
      button.click();
      await vi.waitFor(() => expect(onChange).toHaveBeenCalled());
    });
    expect(reference()).toBe("transform");
    expect(
      container.querySelector('[aria-label="所选积木 ID"]')?.textContent,
    ).toBe("transform");
  };
  await history("撤销");
  expect(checkbox.checked).toBe(false);
  expect(input.value).toBe("Prep");
  await history("撤销");
  expect(input.value).toBe("preprocess");
  await history("重做");
  expect(input.value).toBe("Prep");
  await history("重做");
  expect(checkbox.checked).toBe(true);
  expect(onChange.mock.lastCall![0]).toEqual(manager.serialize());
});

it.each(["name", "role"])(
  "rejects %s conflicts without checking or persisting the rejected object",
  async (conflict) => {
    const initial = fixture();
    const blocks = initial.workspaces.data.blocks.blocks!;
    const other = blocks.find((block) => block.id === "test-dataset")!;
    if (
      !other.fields ||
      typeof other.fields !== "object" ||
      Array.isArray(other.fields)
    )
      throw new Error("Dataset fixture has no field object");
    const id = conflict === "name" ? "transform" : "train-dataset";
    if (conflict === "name")
      other.fields = { ...other.fields, NAME: "preprocess" };
    else {
      other.fields = { ...other.fields, SPLIT: "train" };
      other.extraState = { easyai: { version: 1, registered: true } };
    }
    const { manager, onChange } = await mount(id, false, initial);
    const before = manager.serialize();
    const checkbox = container.querySelector<HTMLInputElement>(
      'input[type="checkbox"]',
    )!;
    act(() => checkbox.click());
    expect(checkbox.checked).toBe(false);
    expect(container.querySelector('[role="alert"]')?.textContent).toContain(
      conflict === "name"
        ? "已有同名对象"
        : "同类训练/测试角色只能注册一个对象",
    );
    expect(manager.serialize()).toEqual(before);
    expect(onChange).not.toHaveBeenCalled();
  },
);

it("readonly registration stays disabled without changing the actual graph", async () => {
  const { manager, onChange } = await mount("transform", true);
  const before = manager.serialize();
  const checkbox = container.querySelector<HTMLInputElement>(
    'input[type="checkbox"]',
  )!;
  expect(checkbox.disabled).toBe(true);
  act(() => checkbox.click());
  expect(checkbox.checked).toBe(false);
  expect(manager.serialize()).toEqual(before);
  expect(onChange).not.toHaveBeenCalled();
});
