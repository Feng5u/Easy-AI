import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { act, createElement, Fragment, useState } from "react";
import type { Root } from "react-dom/client";
import { createRequire } from "node:module";
import { readFileSync } from "node:fs";
import type {
  WorkspaceManager,
  WorkspaceFactory,
  ManagerCallbacks,
} from "./WorkspaceManager.js";
import type {
  DesktopAPI,
  Event,
  ProjectDocument,
  Run,
  RunSource,
  ArtifactRecord,
  AuthenticatedConnection,
} from "../electron/bridge.js";
import { ProjectEditor } from "./ProjectEditor.js";
import { SnapshotCode } from "./RunSnapshot.js";
import { RunDashboard } from "./RunDashboard.js";
import { captureRunSnapshot, locateRunBlock } from "./runSnapshot.js";

// Real Blockly serialization/manager and real React components. Only SVG host
// rendering is replaced by headless handles; this is not Electron acceptance.
const captured = vi.hoisted(() => ({
  managers: [] as { manager: WorkspaceManager; readonly: boolean }[],
}));
vi.mock("./WorkspaceManager.js", async (original) => {
  const actual = await original<typeof import("./WorkspaceManager.js")>();
  const blockly = await import("blockly/core");
  return {
    ...actual,
    WorkspaceManager: class extends actual.WorkspaceManager {
      constructor(
        hosts: Record<"data" | "model" | "training", HTMLElement>,
        readOnly: boolean,
        callbacks: ManagerCallbacks,
      ) {
        const factory: WorkspaceFactory = () => {
          const workspace = new blockly.Workspace();
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
        captured.managers.push({ manager: this, readonly: readOnly });
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
function source(): RunSource {
  const snapshot = JSON.parse(
    readFileSync(
      new URL(
        "../../../packages/contracts/fixtures/mnist.json",
        import.meta.url,
      ),
      "utf8",
    ),
  ) as ProjectDocument;
  snapshot.name = "旧运行的 CNN";
  snapshot.revision = 2;
  return {
    projectRevision: 2,
    programHash: "a".repeat(64),
    codeHash: "b".repeat(64),
    code: "old data code\nold model code\nold training code",
    snapshot,
    sourceMap: (["data", "model", "training"] as const).map((tab, index) => ({
      file: "train.py",
      startLine: index + 1,
      endLine: index + 1,
      kind: "semantic",
      origin: {
        blockId: String(snapshot.workspaces[tab].blocks.blocks![0].id),
        workspace: tab,
      },
    })),
  };
}
function id(saved: RunSource, tab: "data" | "model" | "training") {
  return saved.sourceMap.find((span) => span.origin.workspace === tab)!.origin
    .blockId;
}
function deferred<T>() {
  let resolve!: (value: T) => void;
  const promise = new Promise<T>((done) => {
    resolve = done;
  });
  return { promise, resolve };
}
async function render(element: ReturnType<typeof createElement>) {
  const { createRoot } = await import("react-dom/client");
  root ??= createRoot(container);
  await act(async () => {
    root!.render(element);
  });
}
async function click(text: string) {
  await act(async () => {
    const button = [...container.querySelectorAll("button")].find(
      (item) => item.textContent === text,
    );
    if (!button) throw new Error("Missing button: " + text);
    button.click();
  });
}
beforeEach(() => {
  captured.managers.length = 0;
  dom = new JSDOM("<!doctype html><html><body></body></html>", {
    url: "https://synthetic.test/",
  });
  for (const key of ["window", "document", "navigator", "HTMLElement", "Event"])
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
    "ResizeObserver",
    class {
      observe() {}
      disconnect() {}
    },
  );
  container = dom.window.document.createElement("div");
  dom.window.document.body.append(container);
});
afterEach(async () => {
  if (root) await act(async () => root!.unmount());
  root = undefined;
  vi.unstubAllGlobals();
  dom.window.close();
});

it.each(["rename", "delete", "rebuild"])(
  "locates old blocks despite current-project %s, closes without edits",
  async (change) => {
    const saved = source(),
      current = structuredClone(saved.snapshot),
      before = JSON.stringify(saved);
    current.revision = 7;
    current.name = "当前编辑工程";
    const blockId = id(saved, "model");
    if (change === "rename")
      (
        current.workspaces.model.blocks.blocks![0].fields as Record<
          string,
          unknown
        >
      ).NAME = "CurrentRenamedCNN";
    if (change === "delete") current.workspaces.model.blocks.blocks = [];
    if (change === "rebuild")
      current.workspaces.model.blocks.blocks = [
        { id: blockId, type: "model.relu" },
      ];
    const currentBefore = JSON.stringify(current),
      edited = vi.fn();
    function Screen() {
      const [request, setRequest] = useState<{
        blockId: string;
        version: number;
      } | null>(null);
      return createElement(
        Fragment,
        null,
        createElement(ProjectEditor, {
          project: current,
          readOnly: false,
          selectedBlock: null,
          activeTab: "model",
          onTabChange() {},
          onSelect() {},
          onChange: edited,
        }),
        createElement(
          "button",
          { onClick: () => setRequest({ blockId, version: 1 }) },
          "打开旧产物来源",
        ),
        createElement(SnapshotCode, {
          source: saved,
          request,
          onSelectBlock: (next) =>
            setRequest(next ? { blockId: next, version: 2 } : null),
        }),
      );
    }
    await render(createElement(Screen));
    await click("打开旧产物来源");
    const historical = captured.managers.find((item) => item.readonly)!.manager;
    expect(historical.block(blockId)?.type).toBe("model.define");
    expect(historical.block(blockId)?.getFieldValue("NAME")).not.toBe(
      "CurrentRenamedCNN",
    );
    expect(container.querySelector(".code-selected")?.textContent).toContain(
      "old model code",
    );
    const historyBefore = JSON.stringify(historical.serialize());
    historical.rename(blockId, "CannotEdit");
    historical.remove(blockId);
    historical.register(blockId, false);
    historical.undo();
    expect(JSON.stringify(historical.serialize())).toBe(historyBefore);
    const view = container.querySelector(
      '[aria-label="本次运行的只读积木快照"]',
    )!;
    expect(
      [...view.querySelectorAll("input,button")]
        .filter((item) =>
          ["删除所选积木", "撤销", "重做"].includes(item.textContent ?? ""),
        )
        .every((item) => (item as HTMLButtonElement).disabled),
    ).toBe(true);
    const ids = [...container.querySelectorAll("[role=tabpanel]")].map(
      (item) => item.id,
    );
    expect(new Set(ids).size).toBe(6);
    await act(async () => {
      container
        .querySelector<HTMLButtonElement>(
          `button[aria-label="第 3 行，源积木 ${id(saved, "training")}"]`,
        )!
        .click();
    });
    expect(
      container.querySelector(
        '[aria-label="本次运行的只读积木快照"] [role=tab][aria-selected=true]',
      )?.textContent,
    ).toBe("训练管线");
    expect(container.querySelector(".code-selected")?.textContent).toContain(
      "old training code",
    );
    await click("关闭快照，返回运行结果");
    expect(
      container.querySelector('[aria-label="本次运行的只读积木快照"]'),
    ).toBeNull();
    expect(edited).not.toHaveBeenCalled();
    expect(JSON.stringify(current)).toBe(currentBefore);
    expect(JSON.stringify(saved)).toBe(before);
  },
);

it("locates all three tabs using old spans, repeated requests navigate back and code clicks select old blocks", async () => {
  const saved = source();
  for (const [index, tab] of (
    ["data", "model", "training"] as const
  ).entries()) {
    const blockId = id(saved, tab);
    await render(
      createElement(SnapshotCode, {
        source: saved,
        request: { blockId, version: index },
        onSelectBlock: vi.fn(),
      }),
    );
    const selected = container.querySelector("[role=tab][aria-selected=true]")!;
    expect(selected.textContent).toBe(
      { data: "数据处理", model: "模型结构", training: "训练管线" }[tab],
    );
    expect(container.querySelector(".code-selected")?.textContent).toContain(
      `old ${tab} code`,
    );
  }
  await click("数据处理");
  await render(
    createElement(SnapshotCode, {
      source: saved,
      request: { blockId: id(saved, "training"), version: 4 },
      onSelectBlock: vi.fn(),
    }),
  );
  expect(
    container.querySelector("[role=tab][aria-selected=true]")?.textContent,
  ).toBe("训练管线");
});

it.each([
  "no-spans",
  "missing-block",
  "wrong-tab",
  "future-version",
  "wrong-revision",
  "out-of-range",
])(
  "handles %s without using the current project's ID or guessing code",
  async (variant) => {
    const saved = source(),
      blockId = id(saved, "model");
    if (variant === "no-spans") saved.sourceMap = [];
    if (variant === "missing-block")
      saved.snapshot.workspaces.model.blocks.blocks = [];
    if (variant === "wrong-tab") saved.sourceMap[1].origin.workspace = "data";
    if (variant === "future-version")
      Object.assign(saved.snapshot, { blockLibraryVersion: "9.0.0" });
    if (variant === "wrong-revision") saved.snapshot.revision = 9;
    if (variant === "out-of-range") saved.sourceMap[1].endLine = 900;
    await render(
      createElement(SnapshotCode, {
        source: saved,
        request: { blockId, version: 1 },
        onSelectBlock: vi.fn(),
      }),
    );
    expect(container.querySelector('[role="status"]')?.textContent).toMatch(
      /缺少|不在|不一致|不支持/,
    );
    expect(container.querySelector(".code-selected")).toBeNull();
    if (["future-version", "wrong-revision"].includes(variant))
      expect(captured.managers).toHaveLength(0);
  },
);

it("captures the old snapshot and source map rather than caller-owned mutable objects", () => {
  const saved = source(),
    blockId = id(saved, "model"),
    view = captureRunSnapshot(saved);
  saved.snapshot.name = "mutated later";
  saved.snapshot.workspaces.model.blocks.blocks = [];
  saved.sourceMap[1].origin.blockId = "replaced-later";
  expect(view.snapshot.name).toBe("旧运行的 CNN");
  expect(locateRunBlock(view, blockId)).toMatchObject({
    blockId,
    codeBlockId: blockId,
    workspace: "model",
  });
});

function dashboard(saved: RunSource, runId: string) {
  const run = {
    runId,
    projectId: saved.snapshot.projectId,
    status: "SUCCEEDED",
    connectionState: "connected",
    syncState: "complete",
    config: {
      runId,
      projectId: saved.snapshot.projectId,
      projectRevision: saved.projectRevision,
      programHash: saved.programHash,
      codeHash: saved.codeHash,
      runner: "local",
      executionMode: "full",
      numWorkers: 0,
    },
  } as Run;
  let listener: (event: Event) => void = () => {};
  const image = deferred<{ dataUrl: string }>();
  const artifact = {
    artifactId: "image",
    runId,
    kind: "figure",
    mimeType: "image/png",
    relativePath: "outputs/old.png",
    sizeBytes: 1,
    sha256: "c".repeat(64),
    producerBlockId: id(saved, "training"),
    contributorBlockIds: [],
    syncState: "ready",
  } as ArtifactRecord;
  const api = {
    runs: {
      source: vi.fn(async () => saved),
      get: vi.fn(async () => run),
      logs: vi.fn(async () => ({
        stdout: "",
        stderr: "",
        stdoutAfter: 0,
        stderrAfter: 0,
        done: true,
      })),
      artifacts: vi.fn(async () => [artifact]),
      image: vi.fn(() => image.promise),
      subscribe: vi.fn(
        (_rid: string, _after: number, callback: (event: Event) => void) => {
          listener = callback;
          return vi.fn();
        },
      ),
    },
  } as unknown as DesktopAPI;
  return { run, api, image, emit: (event: Event) => listener(event) };
}

it("artifact and runtime-error clicks open the actual run snapshot and synchronize old code", async () => {
  const saved = source(),
    h = dashboard(saved, "old-run");
  await render(
    createElement(RunDashboard, {
      api: h.api,
      initialRun: h.run,
      onRunUpdate: vi.fn(),
    }),
  );
  await click("来源：" + id(saved, "training"));
  expect(
    container.querySelector("[role=tab][aria-selected=true]")?.textContent,
  ).toBe("训练管线");
  expect(container.querySelector(".code-selected")?.textContent).toContain(
    "old training code",
  );
  await act(async () =>
    h.emit({
      runId: h.run.runId,
      seq: 1,
      source: "runtime",
      sourceSeq: 1,
      timestamp: "2026-10-18T00:00:00Z",
      type: "runtime_error",
      blockId: id(saved, "model"),
      payload: { message: "old model failure" },
    }),
  );
  await click("查看源积木 " + id(saved, "model"));
  expect(
    container.querySelector("[role=tab][aria-selected=true]")?.textContent,
  ).toBe("模型结构");
  expect(container.querySelector(".code-selected")?.textContent).toContain(
    "old model code",
  );
});

it("switching run rejects late source/image/events and does not reopen a closed old snapshot", async () => {
  const oldSource = source(),
    old = dashboard(oldSource, "old"),
    freshSource = source();
  freshSource.snapshot.name = "另一次运行";
  freshSource.code = "fresh data\nfresh model\nfresh training";
  const fresh = dashboard(freshSource, "fresh"),
    late = deferred<RunSource>();
  await render(
    createElement(RunDashboard, {
      api: old.api,
      initialRun: old.run,
      onRunUpdate: vi.fn(),
    }),
  );
  await click("查看图片");
  await click("关闭快照，返回运行结果");
  vi.mocked(old.api.runs.source).mockImplementation(() => late.promise);
  await render(
    createElement(RunDashboard, {
      api: old.api,
      initialRun: { ...old.run, runId: "old-pending" },
      onRunUpdate: vi.fn(),
    }),
  );
  await render(
    createElement(RunDashboard, {
      api: fresh.api,
      initialRun: fresh.run,
      onRunUpdate: vi.fn(),
    }),
  );
  await act(async () => {
    late.resolve(oldSource);
    old.image.resolve({ dataUrl: "data:image/png;base64,OLD" });
    old.emit({
      runId: "old",
      seq: 9,
      source: "application",
      timestamp: "2026-10-18T00:00:00Z",
      type: "runtime_error",
      payload: { message: "late old failure" },
    });
  });
  expect(container.textContent).not.toContain("late old failure");
  expect(container.querySelector(".image-preview img")).toBeNull();
  await click("来源：" + id(freshSource, "training"));
  expect(container.textContent).toContain("另一次运行");
  expect(container.textContent).not.toContain("old training code");
});

it.each(["get", "cancel", "resume"])(
  "rejects a mismatched %s response before changing this run or its source",
  async (operation) => {
    const saved = source(),
      h = dashboard(saved, "owned-run"),
      updated = vi.fn();
    h.run.status = "RUNNING";
    h.run.connectionState = "disconnected";
    h.run.config.runner = "ssh";
    h.run.remote = {
      host: "synthetic.invalid",
      port: 22,
      username: "synthetic",
      hostFingerprint: "SHA256:" + "A".repeat(43),
      executionState: "RUNNING",
      startOutcome: "acknowledged",
      cancelState: "none",
      artifactsVerified: false,
    };
    const foreign = structuredClone(h.run);
    foreign.runId = "foreign-run";
    const session = {
      projectId: h.run.projectId,
      username: "synthetic",
      scope: {
        endpoint: { host: "synthetic.invalid", port: 22 },
        hostFingerprint: h.run.remote.hostFingerprint,
      },
    } as AuthenticatedConnection;
    if (operation === "get")
      vi.mocked(h.api.runs.get).mockResolvedValue(foreign);
    h.api.runs.cancel = vi.fn(async () => foreign);
    h.api.runs.resume = vi.fn(async () => foreign);
    await render(
      createElement(RunDashboard, {
        api: h.api,
        initialRun: h.run,
        onRunUpdate: updated,
        remoteSession: session,
      }),
    );
    updated.mockClear();
    if (operation === "cancel") await click("停止本次运行");
    if (operation === "resume") await click("接续原任务（不重跑）");
    expect(container.textContent).toContain("身份与本次运行不一致");
    expect(container.querySelector(".run-id")?.textContent).toBe("owned-run");
    expect(updated).not.toHaveBeenCalledWith(foreign);
  },
);

it("rejects a source response belonging to another revision/hash", async () => {
  const saved = source(),
    h = dashboard(saved, "owned-run");
  vi.mocked(h.api.runs.source).mockResolvedValue({
    ...saved,
    codeHash: "f".repeat(64),
  });
  await render(
    createElement(RunDashboard, {
      api: h.api,
      initialRun: h.run,
      onRunUpdate: vi.fn(),
    }),
  );
  await click("来源：" + id(saved, "training"));
  expect(container.textContent).toContain("运行快照与本次运行身份不一致");
  expect(captured.managers).toHaveLength(0);
  expect(container.textContent).not.toContain("old training code");
});
