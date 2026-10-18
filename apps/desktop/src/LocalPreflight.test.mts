import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { act, createElement } from "react";
import type { Root } from "react-dom/client";
import { createRequire } from "node:module";
import { mkdtemp, mkdir, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { fileURLToPath } from "node:url";
import { LocalPreflight } from "./LocalPreflight.js";
import type {
  LocalPreflightRequest,
  LocalPreflightResult,
  SelectionResult,
} from "../electron/bridge.js";
import { MainWorkflow } from "../electron/workflow.mjs";
import { startBackend } from "../electron/backend.mjs";
const require = createRequire(import.meta.url);
const { JSDOM } = require(
  require.resolve("jsdom", { paths: [require.resolve("blockly/core")] }),
);
let dom: InstanceType<typeof JSDOM>, root: Root, container: HTMLDivElement;
const projectId = "ba3aef16-eeda-4bb7-8ced-58d6563fb40e";
const pythonId = "bb3aef16-eeda-4bb7-8ced-58d6563fb40e";
const dataId = "bc3aef16-eeda-4bb7-8ced-58d6563fb40e";
const request: LocalPreflightRequest = {
  projectId,
  expectedRevision: 1,
  pythonSelectionId: pythonId,
  dataSelectionId: dataId,
};
function report(value = request): LocalPreflightResult {
  return {
    ...value,
    environment: { ok: true, code: "ENVIRONMENT_READY" },
    data: { ok: false, code: "DATASET_MISSING_NO_DOWNLOAD" },
    versions: {
      python: "/explicit/python",
      prefix: "/explicit",
      torch: "test-torch",
      torchvision: "test-vision",
      matplotlib: "test-plot",
    },
    datasetNames: ["MNIST"],
  };
}
beforeEach(async () => {
  dom = new JSDOM("<!doctype html><html><body></body></html>", {
    url: "http://localhost",
  });
  vi.stubGlobal("window", dom.window);
  vi.stubGlobal("document", dom.window.document);
  vi.stubGlobal("navigator", dom.window.navigator);
  vi.stubGlobal("IS_REACT_ACT_ENVIRONMENT", true);
  container = document.createElement("div");
  document.body.append(container);
  const { createRoot } = await import("react-dom/client");
  root = createRoot(container);
});
afterEach(async () => {
  await act(async () => root.unmount());
  dom.window.close();
  vi.unstubAllGlobals();
});
async function mount(
  preflight: (value: LocalPreflightRequest) => Promise<LocalPreflightResult>,
  value = request,
  disabled = false,
) {
  await act(async () =>
    root.render(
      createElement(LocalPreflight, {
        key: JSON.stringify(value),
        api: { preflight },
        request: value,
        pythonLabel: "chosen Python",
        dataLabel: "chosen data",
        disabled,
      }),
    ),
  );
}
async function click() {
  await act(async () =>
    (container.querySelector("button") as HTMLButtonElement).click(),
  );
}
function deferred<T>() {
  let resolve!: (value: T) => void, reject!: (reason: unknown) => void;
  const promise = new Promise<T>((a, b) => {
    resolve = a;
    reject = b;
  });
  return { promise, resolve, reject };
}
it("requires explicit click, reports dependency and data separately, and repeats only on request", async () => {
  const preflight = vi.fn().mockResolvedValue(report());
  await mount(preflight);
  expect(preflight).not.toHaveBeenCalled();
  await click();
  expect(preflight).toHaveBeenCalledExactlyOnceWith(request);
  expect(container.textContent).toContain("环境：可用");
  expect(container.textContent).toContain("数据（MNIST）：未通过");
  expect(container.textContent).toContain("未下载数据");
  expect(container.textContent).toContain("test-torch");
  await click();
  expect(preflight).toHaveBeenCalledTimes(2);
});
it("disables dirty or active state and keeps one in-flight check", async () => {
  const task = deferred<LocalPreflightResult>(),
    preflight = vi.fn(() => task.promise);
  await mount(preflight, request, true);
  await click();
  expect(preflight).not.toHaveBeenCalled();
  await mount(preflight);
  await click();
  await click();
  expect(preflight).toHaveBeenCalledTimes(1);
  await act(async () => task.resolve(report()));
});
it.each([
  "projectId",
  "pythonSelectionId",
  "dataSelectionId",
  "expectedRevision",
] as const)("keyed %s change discards old success and error", async (field) => {
  for (const rejects of [false, true]) {
    const task = deferred<LocalPreflightResult>(),
      preflight = vi.fn(() => task.promise);
    await mount(preflight);
    await click();
    const next = {
      ...request,
      [field]:
        field === "expectedRevision"
          ? 2
          : "bd3aef16-eeda-4bb7-8ced-58d6563fb40e",
    };
    await mount(preflight, next);
    await act(async () => {
      if (rejects) task.reject(new Error("old-error"));
      else task.resolve(report());
    });
    expect(container.textContent).not.toContain("test-torch");
    expect(container.textContent).not.toContain("old-error");
    expect(container.textContent).not.toContain("正在检查");
    await act(async () => root.render(null));
  }
});
it("rejects a foreign result and explains environment failure without blaming code", async () => {
  await mount(async () => report({ ...request, expectedRevision: 2 }));
  await click();
  expect(container.textContent).toContain("检查报告与当前选择不一致");
  expect(container.textContent).not.toContain("test-torch");
  await mount(async () => ({
    ...report(),
    environment: { ok: false, code: "ENVIRONMENT_IMPORT_FAILED" },
    versions: null,
  }));
  await click();
  expect(container.textContent).toContain("无法导入");
  expect(container.textContent).toContain("缺少预期的 IDX");
});
it("real React → Main → authenticated sidecar → fixed import/data checks, without training", async () => {
  const directory = await mkdtemp(join(tmpdir(), "easyai-local-preflight-"));
  const cwd = fileURLToPath(
    new URL("../../../services/backend/", import.meta.url),
  );
  const python = join(
    cwd,
    process.platform === "win32"
      ? ".venv/Scripts/python.exe"
      : ".venv/bin/python",
  );
  const backend = await startBackend(
    python,
    cwd,
    10000,
    join(directory, "state"),
  );
  let chosen = directory;
  const workflow = new MainWorkflow(
    () => backend,
    async () => chosen,
    () => undefined,
  );
  try {
    const selection = async (kind: string) =>
      (await workflow.invoke("easyai:selections:pick", [
        kind,
      ])) as SelectionResult;
    const project = await selection("project");
    const session = (await workflow.invoke("easyai:projects:create", [
      project.selectionId,
      "预检测试",
    ])) as { project: { projectId: string; revision: number } };
    chosen = python;
    const interpreter = await selection("python");
    chosen = join(directory, "empty-data");
    await mkdir(chosen);
    const data = await selection("data");
    const value = {
      projectId: session.project.projectId,
      expectedRevision: session.project.revision,
      pythonSelectionId: interpreter.selectionId,
      dataSelectionId: data.selectionId,
    };
    const preflight = vi.fn(
      async (input: LocalPreflightRequest) =>
        (await workflow.invoke("easyai:local:preflight", [
          input,
        ])) as LocalPreflightResult,
    );
    await mount(preflight, value);
    expect(preflight).not.toHaveBeenCalled();
    await click();
    await act(async () => {
      await preflight.mock.results[0].value;
    });
    expect(container.textContent).toContain("ENVIRONMENT_IMPORT_FAILED");
    expect(container.textContent).toContain("DATASET_MISSING_NO_DOWNLOAD");
    expect(
      await workflow.invoke("easyai:runs:list", [value.projectId, 0, 25]),
    ).toEqual([]);
  } finally {
    workflow.dispose();
    await backend.stop();
    await rm(directory, { recursive: true, force: true });
  }
}, 20000);
