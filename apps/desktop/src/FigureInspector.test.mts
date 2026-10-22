import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { act, createElement, useState } from "react";
import type { Root } from "react-dom/client";
import { createRequire } from "node:module";
import { readFileSync } from "node:fs";
import { mkdtemp, rm } from "node:fs/promises";
import { spawnSync } from "node:child_process";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { fileURLToPath } from "node:url";
import {
  WorkspaceManager,
  canonical,
  figureLayouts,
  figureSizes,
} from "./WorkspaceManager.js";
import type { ManagerCallbacks, WorkspaceFactory } from "./WorkspaceManager.js";
import type { ProjectDocument, RunSource } from "../electron/bridge.js";
import { ProjectEditor } from "./ProjectEditor.js";
import { SnapshotCode } from "./RunSnapshotCode.js";
const captured = vi.hoisted(() => ({
  managers: [] as WorkspaceManager[],
  selections: [] as (string | null)[],
}));
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
        const factory: WorkspaceFactory = () => {
          const workspace = new Blockly.Workspace();
          return {
            workspace,
            resize() {},
            setVisible() {},
            setReadOnly() {},
            select(id) {
              captured.selections.push(id);
            },
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
  root: Root | undefined,
  container: HTMLDivElement;
function fixture(): ProjectDocument {
  return JSON.parse(
    readFileSync(
      new URL(
        "../../../packages/contracts/fixtures/mnist-figures.json",
        import.meta.url,
      ),
      "utf8",
    ),
  );
}
const settle = () => new Promise<void>((resolve) => setTimeout(resolve, 20));
function setup(readOnly = false) {
  const callbacks = {
    onChange: vi.fn(),
    onSelect: vi.fn(),
    onTabChange: vi.fn(),
    onRefresh: vi.fn(),
  };
  const manager = new WorkspaceManager(
    {
      data: {} as HTMLElement,
      model: {} as HTMLElement,
      training: {} as HTMLElement,
    },
    readOnly,
    callbacks,
  );
  manager.receive(fixture().workspaces);
  return { manager, callbacks };
}
beforeEach(() => {
  captured.managers.length = 0;
  captured.selections.length = 0;
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
  vi.stubGlobal(
    "ResizeObserver",
    class {
      observe() {}
      disconnect() {}
    },
  );
  container = document.createElement("div");
  document.body.append(container);
});
afterEach(async () => {
  if (root) await act(async () => root!.unmount());
  root = undefined;
  captured.managers.forEach((manager) => manager.dispose());
  dom.window.close();
  vi.unstubAllGlobals();
});
it.each(
  figureLayouts.flatMap((layout) =>
    figureSizes.map((size) => ({ layout, size })),
  ),
)(
  "real Blockly supports $layout / $size without changing IDs or panel order",
  async ({ layout, size }) => {
    const { manager } = setup();
    const ids = manager.workspaces.training
      .getAllBlocks(false)
      .map((block) => block.id)
      .sort();
    manager.configureFigure("before-figure", layout, size);
    await settle();
    expect(manager.figure("before-0-panel")).toEqual(
      expect.objectContaining({
        id: "before-figure",
        layout,
        size,
        panels: [expect.objectContaining({ id: "before-0-panel" })],
      }),
    );
    expect(
      manager.workspaces.training
        .getAllBlocks(false)
        .map((block) => block.id)
        .sort(),
    ).toEqual(ids);
  },
);
it("applies two fields in one Undo/Redo group and navigates the actual workspace before undo", async () => {
  const { manager, callbacks } = setup();
  manager.setActive("data");
  await settle();
  manager.workspaces.training.clearUndo();
  manager.configureFigure("before-figure", "2,2", "large");
  await settle();
  expect(callbacks.onTabChange).toHaveBeenLastCalledWith("training");
  expect(manager.figure("before-figure")).toEqual(
    expect.objectContaining({ layout: "2,2", size: "large" }),
  );
  manager.undo();
  await settle();
  expect(manager.figure("before-figure")).toEqual(
    expect.objectContaining({ layout: "1,1", size: "medium" }),
  );
  manager.undo(true);
  await settle();
  expect(manager.figure("before-figure")).toEqual(
    expect.objectContaining({ layout: "2,2", size: "large" }),
  );
});
it("rejects shrinking across disabled panels before any field or connection change", async () => {
  const { manager, callbacks } = setup();
  manager.block("body-0-panel")!.setDisabledReason(true, "test-disable");
  await settle();
  callbacks.onChange.mockClear();
  const before = canonical(manager.serialize());
  expect(
    manager
      .figure("body-1-panel")!
      .panels.map((panel) => [panel.id, panel.disabled]),
  ).toEqual([
    ["body-0-panel", true],
    ["body-1-panel", false],
  ]);
  expect(() => manager.configureFigure("body-figure", "1,1", "large")).toThrow(
    "含停用块",
  );
  await settle();
  expect(canonical(manager.serialize())).toBe(before);
  expect(callbacks.onChange).not.toHaveBeenCalled();
  for (const [layout, size] of [
    ["8,8", "large"],
    ["2,2", "unknown"],
  ])
    expect(() =>
      manager.configureFigure("body-figure", layout, size),
    ).toThrow();
  expect(canonical(manager.serialize())).toBe(before);
});
it("readonly rejects programmatic edits and no-op field application emits no semantic change", async () => {
  const { manager, callbacks } = setup(true);
  const before = canonical(manager.serialize());
  manager.configureFigure("before-figure", "2,5", "large");
  await settle();
  expect(canonical(manager.serialize())).toBe(before);
  expect(callbacks.onChange).not.toHaveBeenCalled();
  manager.setReadOnly(false);
  manager.configureFigure("before-figure", "1,1", "medium");
  await settle();
  expect(callbacks.onChange).not.toHaveBeenCalled();
});
async function render(element: ReturnType<typeof createElement>) {
  const { createRoot } = await import("react-dom/client");
  root ??= createRoot(container);
  await act(async () => root!.render(element));
}
async function click(text: string) {
  await act(async () => {
    const button = [...container.querySelectorAll("button")].find(
      (node) => node.textContent === text,
    );
    if (!button) throw new Error(text);
    button.click();
    await settle();
  });
}
async function select(label: string, value: string) {
  await act(async () => {
    const input = [...container.querySelectorAll("label")]
      .find((node) => node.textContent?.startsWith(label))!
      .querySelector("select")!;
    Object.getOwnPropertyDescriptor(
      dom.window.HTMLSelectElement.prototype,
      "value",
    )!.set!.call(input, value);
    input.dispatchEvent(new dom.window.Event("change", { bubbles: true }));
  });
}
function screen(project: ProjectDocument, readOnly = false) {
  return function Screen() {
    const [value, setValue] = useState(project);
    const [selected, setSelected] = useState<string | null>("body-figure");
    const [tab, setTab] = useState<"data" | "model" | "training">("training");
    return createElement(ProjectEditor, {
      project: value,
      readOnly,
      selectedBlock: selected,
      activeTab: tab,
      onTabChange: setTab,
      onSelect: setSelected,
      onChange: (workspaces) => setValue((old) => ({ ...old, workspaces })),
    });
  };
}
it("DOM edits real blocks, keeps panel grid while locating, and Undo resynchronizes controls", async () => {
  const Screen = screen(fixture());
  await render(createElement(Screen));
  expect(
    container.querySelectorAll("select")[0].querySelectorAll("option"),
  ).toHaveLength(5);
  expect(
    container.querySelectorAll("select")[1].querySelectorAll("option"),
  ).toHaveLength(3);
  await select("画布布局", "2,2");
  await select("画布尺寸", "large");
  await click("应用布局与尺寸");
  const manager = captured.managers[0];
  expect(manager.figure("body-figure")).toEqual(
    expect.objectContaining({ layout: "2,2", size: "large" }),
  );
  const grid = container.querySelector('ol[aria-label="启用子图运行网格"]')!;
  expect(grid.children).toHaveLength(4);
  await act(async () => {
    (grid.querySelectorAll("button")[1] as HTMLButtonElement).click();
  });
  expect(captured.selections).toContain("body-1-panel");
  expect(container.textContent).toContain("画布布局与子图");
  await click("撤销");
  expect(container.querySelector<HTMLSelectElement>("select")!.value).toBe(
    "1,2",
  );
  expect(manager.figure("body-figure")!.size).toBe("medium");
  await click("重做");
  expect(manager.figure("body-figure")!.layout).toBe("2,2");
});
it("runtime grid skips disabled chain head like Python, while full chain remains locatable", async () => {
  const project = fixture();
  const { manager } = setup();
  manager.block("body-0-panel")!.setDisabledReason(true, "test-disable");
  await settle();
  project.workspaces = manager.serialize();
  manager.dispose();
  await render(createElement(screen(project)));
  const grid = container.querySelector('ol[aria-label="启用子图运行网格"]')!;
  expect(grid.querySelectorAll("button")).toHaveLength(1);
  expect(grid.querySelector("li button")!.textContent).toContain(
    "body-1-panel",
  );
  expect(grid.querySelector("li button")!.getAttribute("aria-label")).toContain(
    "第 1 行，第 1 列",
  );
  expect(
    container.querySelector('ol[aria-label="全部已连接子图"]')!.textContent,
  ).toContain("body-0-panel");
  await select("画布布局", "1,1");
  await click("应用布局与尺寸");
  expect(container.textContent).toContain("含停用块");
  expect(captured.managers.at(-1)!.figure("body-figure")!.layout).toBe("1,2");
});
it("actual historical SnapshotCode exposes readonly inspector navigation without changing its snapshot", async () => {
  const scroll = vi.fn();
  dom.window.HTMLElement.prototype.scrollIntoView = scroll;
  const project = fixture();
  const before = canonical(project);
  const source: RunSource = {
    snapshot: project,
    projectRevision: project.revision,
    programHash: "a".repeat(64),
    codeHash: "b".repeat(64),
    code: "# UI source fixture\n",
    sourceMap: [
      {
        startLine: 1,
        endLine: 1,
        origin: { blockId: "body-figure", workspace: "training" },
        kind: "semantic",
      },
    ],
  };
  const onSelectBlock = vi.fn();
  await render(
    createElement(SnapshotCode, {
      source,
      request: { blockId: "body-figure", version: 1 },
      onSelectBlock,
    }),
  );
  const until = Date.now() + 1500;
  while (!container.querySelector("select") && Date.now() < until)
    await act(async () => {
      await settle();
    });
  expect(scroll).toHaveBeenCalledWith({
    block: "nearest",
    inline: "nearest",
    behavior: "instant",
  });
  expect(container.querySelectorAll("select")).toHaveLength(2);
  expect(
    [...container.querySelectorAll("select")].every((input) => input.disabled),
  ).toBe(true);
  const manager = captured.managers.at(-1)!;
  const saved = canonical(manager.serialize());
  manager.configureFigure("body-figure", "2,2", "large");
  expect(canonical(manager.serialize())).toBe(saved);
  expect(canonical(project)).toBe(before);
  const grid = container.querySelector('ol[aria-label="启用子图运行网格"]')!;
  expect((grid.querySelector("button") as HTMLButtonElement).disabled).toBe(
    false,
  );
  await act(async () => {
    (grid.querySelector("button") as HTMLButtonElement).click();
  });
  expect(onSelectBlock).toHaveBeenCalledWith("body-0-panel", false);
  expect(captured.selections.at(-1)).toBe("body-0-panel");
  expect(canonical(project)).toBe(before);
});
it("real Blockly edits survive ProjectService save/reopen with deterministic Python code/hash/map", async () => {
  const original = fixture();
  const { manager } = setup();
  manager.block("body-0-panel")!.setDisabledReason(true, "test-disable");
  manager.configureFigure("body-figure", "2,2", "large");
  await settle();
  const edited = { ...original, workspaces: manager.serialize() };
  const rootPath = await mkdtemp(join(tmpdir(), "easyai-figure-save-"));
  const backend = fileURLToPath(
    new URL("../../../services/backend/", import.meta.url),
  );
  const script = `import ast,json,sys\nfrom pathlib import Path\nfrom easyai.domain.contracts import ProjectDocument\nfrom easyai.services.project_service import ProjectService,read_project\nfrom easyai.compiler.pipeline import compile_project\nroot=Path(sys.argv[1]); payload=json.load(sys.stdin)\noriginal=ProjectDocument.model_validate(payload['original']); edited=ProjectDocument.model_validate(payload['edited'])\n(root/'project.easyai.json').write_text(original.model_dump_json(by_alias=True))\nservice=ProjectService(root)\ntry: saved=service.save(edited,original.revision)\nfinally: service.close()\nreopened=ProjectService(root)\ntry: document=reopened.snapshot(saved.revision).document\nfinally: reopened.close()\na=compile_project(edited); b=compile_project(document); assert a.result.runnable and b.result.runnable\nast.parse(b.result.code)\nassert a.result.code==b.result.code and a.result.code_hash==b.result.code_hash and a.result.program_hash==b.result.program_hash and a.result.source_map==b.result.source_map\nassert [p.origin.block_id for p in b.program.training.body[0].panels]==['body-1-panel']\nspans=[s for s in b.result.source_map if s.origin.block_id=='body-1-panel']; lines=b.result.code.splitlines(); assert any('grid[0]' in lines[s.start_line-1] for s in spans)\nassert 'fig.add_gridspec(2, 2)' in b.result.code and 'figsize=(14, 8)' in b.result.code\nprint(json.dumps(document.model_dump(mode='json',by_alias=True)))`;
  try {
    const result = spawnSync(
      join(
        backend,
        process.platform === "win32"
          ? ".venv/Scripts/python.exe"
          : ".venv/bin/python",
      ),
      ["-c", script, rootPath],
      {
        cwd: backend,
        input: JSON.stringify({ original, edited }),
        encoding: "utf8",
        timeout: 10000,
      },
    );
    expect(result.status, result.stderr).toBe(0);
    const reopened = JSON.parse(result.stdout) as ProjectDocument;
    expect(reopened.revision).toBe(2);
    expect(reopened.workspaces).toEqual(edited.workspaces);
    manager.receive(reopened.workspaces);
    expect(
      manager
        .figure("body-figure")!
        .panels.map((panel) => [panel.id, panel.disabled]),
    ).toEqual([
      ["body-0-panel", true],
      ["body-1-panel", false],
    ]);
  } finally {
    await rm(rootPath, { recursive: true, force: true });
  }
});
