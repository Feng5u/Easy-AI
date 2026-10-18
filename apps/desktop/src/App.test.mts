/// <reference types="node" />
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { act, createElement } from "react";
import type { Root } from "react-dom/client";
import { createRequire } from "node:module";
import { mkdtemp, mkdir, readFile, writeFile, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { fileURLToPath } from "node:url";
import { startBackend } from "../electron/backend.mjs";
import { MainWorkflow } from "../electron/workflow.mjs";
import type { SelectionResult } from "../electron/bridge.js";
import type {
  DesktopAPI,
  ProjectDocument,
  ProjectSession,
} from "../electron/bridge.js";
import type { ProjectEditorProps } from "./editor-contract.js";
import { App } from "./App.js";

vi.mock("./ProjectEditor.js", async () => {
  const { createElement: element } = await import("react");
  return {
    ProjectEditor(props: ProjectEditorProps) {
      const blocks = props.project.workspaces.model.blocks.blocks ?? [];
      return element(
        "section",
        { "aria-label": "unit-test canvas" },
        element("output", { "data-testid": "visible-tab" }, props.activeTab),
        element(
          "output",
          { "data-testid": "visible-blocks" },
          String(blocks.length),
        ),
        element(
          "button",
          { onClick: () => props.onTabChange("model") },
          "画布模型页",
        ),
        element(
          "button",
          { onClick: () => props.onTabChange("training") },
          "画布训练页",
        ),
        element(
          "button",
          {
            disabled: props.readOnly,
            onClick: () =>
              props.onChange({
                ...props.project.workspaces,
                model: {
                  blocks: {
                    blocks: [
                      ...blocks,
                      { type: "model.relu", id: `unit-layer-${blocks.length}` },
                    ],
                  },
                },
              }),
          },
          "画布新增层",
        ),
      );
    },
  };
});

const require = createRequire(import.meta.url);
const { JSDOM } = require(
  require.resolve("jsdom", { paths: [require.resolve("blockly/core")] }),
);
let dom: InstanceType<typeof JSDOM>;
let root: Root | undefined;
let container: HTMLDivElement;

function project(): ProjectDocument {
  return {
    projectId: "bafed894-4d08-4350-994b-c43211bd2622",
    name: "真实组件测试工程",
    revision: 1,
    workspaces: {
      data: { blocks: { blocks: [] } },
      model: { blocks: { blocks: [] } },
      training: { blocks: { blocks: [] } },
    },
    ui: { activeTab: "data", codeVisible: false },
    settings: { executionMode: "full" },
  };
}
function bridge(readOnly = false) {
  const unsubscribe = vi.fn();
  const save = vi.fn<DesktopAPI["projects"]["save"]>(
    async (value, revision) => ({
      project: { ...value, revision: revision + 1 },
      readOnly: false,
    }),
  );
  const exported = vi
    .fn<DesktopAPI["projects"]["exportProject"]>()
    .mockResolvedValue({ exported: true });
  const dirty = vi
    .fn<DesktopAPI["projects"]["setDirty"]>()
    .mockResolvedValue(undefined);
  const unsupported = async (): Promise<never> => {
    throw new Error("Unexpected operation in component unit test");
  };
  const api: DesktopAPI = {
    local: { preflight: unsupported },
    environments: {
      discover: unsupported,
      probe: unsupported,
      cancel: unsupported,
    },
    connections: {
      authenticate: unsupported,
      cancelAuth: async () => {},
      close: async () => {},
      current: async () => null,
      probe: unsupported,
      confirm: unsupported,
      cancel: async () => {},
    },
    status: {
      get: async () => ({ ready: true, message: "ready" }),
      subscribe: () => unsubscribe,
    },
    selections: { pick: async () => null },
    projects: {
      current: async () => ({
        project: project(),
        readOnly,
        reason: readOnly ? "PROJECT_LOCK_HELD" : null,
      }),
      setDirty: dirty,
      open: unsupported,
      create: unsupported,
      importProject: async () => null,
      exportProject: exported,
      save,
      compile: unsupported,
    },
    runs: {
      bind: async () => {
        throw new Error("remote binding not configured in this local fixture");
      },
      resume: async () => {
        throw new Error("remote resume not configured in this local fixture");
      },
      list: async () => [],
      start: unsupported,
      get: unsupported,
      cancel: unsupported,
      source: unsupported,
      logs: unsupported,
      artifacts: unsupported,
      image: unsupported,
      subscribe: () => () => {},
    },
  };
  return { api, save, exported, dirty, unsubscribe };
}
function button(label: string): HTMLButtonElement {
  const target = Array.from(container.querySelectorAll("button")).find(
    (node) => node.textContent === label,
  );
  if (!target)
    throw new Error(`Button missing: ${label}; ${container.textContent}`);
  return target;
}
async function click(label: string) {
  await act(async () => {
    button(label).click();
  });
}
async function advance(ms: number) {
  await act(async () => {
    await vi.advanceTimersByTimeAsync(ms);
  });
}
async function mount(api: DesktopAPI) {
  await import("./ProjectEditor.js");
  const { createRoot } = await import("react-dom/client");
  root = createRoot(container);
  await act(async () => {
    root!.render(createElement(App, { api }));
  });
  // Settle the actual lazy boundary, including React's deferred commit, within
  // a bounded fake-clock window before any edits or autosave assertions.
  for (let attempt = 0; attempt < 50; attempt++) {
    if (container.querySelector('[data-testid="visible-tab"]')) break;
    await act(async () => {
      await new Promise<void>((resolve) => setImmediate(resolve));
      await vi.advanceTimersByTimeAsync(20);
    });
  }
  expect(container.querySelector('[data-testid="visible-tab"]')).not.toBeNull();
}

beforeEach(() => {
  dom = new JSDOM("<!doctype html><html><body></body></html>", {
    url: "https://component.test/",
  });
  vi.stubGlobal("window", dom.window);
  vi.stubGlobal("document", dom.window.document);
  vi.stubGlobal("navigator", dom.window.navigator);
  vi.stubGlobal("HTMLElement", dom.window.HTMLElement);
  vi.stubGlobal("Node", dom.window.Node);
  vi.stubGlobal("IS_REACT_ACT_ENVIRONMENT", true);
  container = document.createElement("div");
  document.body.appendChild(container);
  vi.useFakeTimers({ toFake: ["setTimeout", "clearTimeout"] });
});
afterEach(async () => {
  if (root) {
    await act(async () => root!.unmount());
    root = undefined;
  }
  vi.useRealTimers();
  vi.unstubAllGlobals();
  dom.window.close();
});

describe("real App DOM persistence lifecycle", () => {
  it("exports clean noncanonical JSON byte-exact through real App, Main workflow and sidecar", async () => {
    const directory = await mkdtemp(join(tmpdir(), "easyai-clean-export-"));
    const chosen = join(directory, "original");
    const destination = join(directory, "portable.json");
    await mkdir(chosen);
    const fixture = JSON.parse(
      await readFile(
        new URL(
          "../../../packages/contracts/fixtures/blank.json",
          import.meta.url,
        ),
        "utf8",
      ),
    );
    const original = Buffer.from(
      JSON.stringify(
        Object.fromEntries(Object.entries(fixture).reverse()),
        null,
        "\t",
      ) + "\n\n",
    );
    await writeFile(join(chosen, "project.easyai.json"), original);
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
      join(directory, "state"),
    );
    const workflow = new MainWorkflow(
      () => backend,
      async () => chosen,
      () => undefined,
      {
        importProject: async () => null,
        exportProject: async () => destination,
      },
    );
    try {
      const selected = (await workflow.invoke("easyai:selections:pick", [
        "project",
      ])) as SelectionResult;
      await workflow.invoke("easyai:projects:open", [selected.selectionId]);
      const mocked = bridge();
      mocked.api.projects.current = async () =>
        (await workflow.invoke(
          "easyai:projects:current",
          [],
        )) as ProjectSession;
      mocked.api.projects.exportProject = vi.fn(
        async (document) =>
          (await workflow.invoke(
            "easyai:projects:export",
            document ? [document] : [],
          )) as { exported: boolean },
      );
      mocked.api.runs.list = async (id, offset, limit) =>
        (await workflow.invoke("easyai:runs:list", [id, offset, limit])) as [];
      await mount(mocked.api);
      await click("导出当前工程");
      await act(async () => {
        await vi.mocked(mocked.api.projects.exportProject).mock.results[0]
          .value;
      });
      expect(
        vi.mocked(mocked.api.projects.exportProject).mock.calls[0][0],
      ).toBeUndefined();
      expect(await readFile(destination)).toEqual(original);
      expect(await readFile(join(chosen, "project.easyai.json"))).toEqual(
        original,
      );
      expect(container.textContent).toContain("已导出工程原件");
    } finally {
      if (root) {
        await act(async () => root!.unmount());
        root = undefined;
      }
      workflow.dispose();
      await backend.stop();
      await rm(directory, { recursive: true, force: true });
    }
  }, 20000);
  it("switches readonly viewing tabs without dirtying or saving the original project", async () => {
    const mocked = bridge(true);
    await mount(mocked.api);
    expect(
      container.querySelector('[data-testid="visible-tab"]')?.textContent,
    ).toBe("data");
    await click("画布模型页");
    expect(
      container.querySelector('[data-testid="visible-tab"]')?.textContent,
    ).toBe("model");
    await click("画布训练页");
    expect(
      container.querySelector('[data-testid="visible-tab"]')?.textContent,
    ).toBe("training");
    await advance(2400);
    expect(mocked.save).not.toHaveBeenCalled();
    expect(mocked.dirty.mock.calls.every(([value]) => value === false)).toBe(
      true,
    );
    expect(button("画布新增层").disabled).toBe(true);
  });
  it("autosaves after 800ms and preserves edits made while that save is pending", async () => {
    const mocked = bridge();
    let acknowledge!: (session: ProjectSession) => void;
    mocked.save.mockImplementationOnce(
      () =>
        new Promise((resolve) => {
          acknowledge = resolve;
        }),
    );
    await mount(mocked.api);
    await click("画布新增层");
    await advance(799);
    expect(mocked.save).not.toHaveBeenCalled();
    await advance(1);
    expect(mocked.save).toHaveBeenCalledTimes(1);
    const [first, revision] = mocked.save.mock.calls[0];
    expect(revision).toBe(1);
    expect(first.workspaces.model.blocks.blocks).toHaveLength(1);
    await click("画布新增层");
    expect(
      container.querySelector('[data-testid="visible-blocks"]')?.textContent,
    ).toBe("2");
    await act(async () => {
      acknowledge({ project: { ...first, revision: 2 }, readOnly: false });
    });
    expect(
      container.querySelector('[data-testid="visible-blocks"]')?.textContent,
    ).toBe("2");
    expect(container.textContent).toContain("有未保存配置");
    await advance(800);
    expect(mocked.save).toHaveBeenCalledTimes(2);
    const [second, expected] = mocked.save.mock.calls[1];
    expect(expected).toBe(2);
    expect(second.workspaces.model.blocks.blocks).toHaveLength(2);
    expect(container.textContent).toContain("revision 3");
    expect(container.textContent).not.toContain("有未保存配置");
    await act(async () => root!.unmount());
    root = undefined;
    expect(mocked.unsubscribe).toHaveBeenCalledOnce();
  });
  it("retains a conflicted draft, pauses automatic saving and exports that exact draft", async () => {
    const mocked = bridge();
    mocked.save.mockRejectedValue(new Error("PROJECT_REVISION_CONFLICT"));
    await mount(mocked.api);
    await click("画布新增层");
    await advance(800);
    expect(container.textContent).toContain("自动保存已暂停");
    expect(container.textContent).toContain("有未保存配置");
    expect(
      container.querySelector('[data-testid="visible-blocks"]')?.textContent,
    ).toBe("1");
    await advance(4000);
    expect(mocked.save).toHaveBeenCalledTimes(1);
    await click("导出当前工程");
    expect(mocked.exported).toHaveBeenCalledOnce();
    expect(
      mocked.exported.mock.calls[0][0]?.workspaces.model.blocks.blocks,
    ).toHaveLength(1);
    expect(mocked.exported.mock.calls[0][0]?.revision).toBe(1);
    expect(container.textContent).toContain("当前未保存草稿已导出为新文件");
    expect(mocked.dirty).toHaveBeenLastCalledWith(true);
  });
});

it("opens the normal SSH identity panel and closes without authenticating", async () => {
  const { api } = bridge();
  const probe = vi.fn<DesktopAPI["connections"]["probe"]>(
    async (projectId, requestId, endpoint) => ({
      projectId,
      requestId,
      observation: {
        endpoint,
        algorithm: "ssh-ed25519",
        fingerprint: "SHA256:" + "A".repeat(43),
        trustState: "unknown",
        challengeId: "44444444-4444-4444-8444-444444444444",
      },
    }),
  );
  const cancel = vi.fn<DesktopAPI["connections"]["cancel"]>(async () => {});
  api.connections.probe = probe;
  api.connections.cancel = cancel;
  await mount(api);
  await click("SSH 主机身份设置");
  expect(container.textContent).toContain("不登录、不上传或运行任务");
  await act(async () => {
    const input = container.querySelector(
      'section[aria-labelledby="ssh-identity-heading"] input',
    )!;
    Object.getOwnPropertyDescriptor(
      dom.window.HTMLInputElement.prototype,
      "value",
    )!.set!.call(input, "offline.invalid");
    input.dispatchEvent(new dom.window.Event("input", { bubbles: true }));
  });
  await click("检查主机指纹");
  expect(probe).toHaveBeenCalledTimes(1);
  expect(button("确认信任此指纹").disabled).toBe(true);
  await click("关闭主机身份");
  expect(container.querySelector("#ssh-identity-heading")).toBeNull();
  expect(cancel).toHaveBeenCalledWith(
    project().projectId,
    probe.mock.calls[0][1],
  );
});

it("opens normal SSH authentication and explicit environment discovery through App controls", async () => {
  const { api } = bridge();
  const pid = project().projectId;
  const cid = "33333333-3333-4333-8333-333333333333";
  const environmentId = "44444444-4444-4444-8444-444444444444";
  const scope = {
    projectId: pid,
    connectionId: cid,
    endpoint: { host: "synthetic.invalid", port: 22 },
    hostFingerprint: "SHA256:" + "A".repeat(43),
  };
  api.connections.probe = async (projectId, requestId, endpoint) => ({
    projectId,
    requestId,
    observation: {
      endpoint,
      algorithm: "ssh-ed25519",
      fingerprint: scope.hostFingerprint,
      trustState: "trusted",
    },
  });
  api.connections.authenticate = vi.fn<
    DesktopAPI["connections"]["authenticate"]
  >(async (projectId, requestId, identityRequestId, username, password) => {
    expect(password).toBe("synthetic-memory-only");
    expect(
      container.querySelector<HTMLInputElement>('input[type="password"]')!
        .value,
    ).toBe("");
    return {
      projectId,
      requestId,
      identityRequestId,
      username,
      scope,
      authenticated: true,
      method: "password",
      expiresInSeconds: 300,
    };
  });
  const close = vi.fn(async () => {});
  api.connections.close = close;
  api.environments.discover = vi.fn<DesktopAPI["environments"]["discover"]>(
    async (request) => ({
      ...request,
      scope,
      environments: [
        {
          environmentId,
          kind: "python",
          location: "/synthetic/python",
          readOnly: true,
        },
      ],
      note: "unprobed",
    }),
  );
  await mount(api);
  await click("SSH 主机身份设置");
  async function enter(label: string, value: string) {
    await act(async () => {
      const input = [...container.querySelectorAll("label")]
        .find((node) => node.textContent?.startsWith(label))!
        .querySelector("input")!;
      Object.getOwnPropertyDescriptor(
        dom.window.HTMLInputElement.prototype,
        "value",
      )!.set!.call(input, value);
      input.dispatchEvent(new dom.window.Event("input", { bubbles: true }));
    });
  }
  await enter("主机名或 IP", "synthetic.invalid");
  await click("检查主机指纹");
  expect(api.connections.authenticate).not.toHaveBeenCalled();
  await enter("SSH 用户名", "synthetic");
  await enter("SSH 密码", "synthetic-memory-only");
  await click("认证并建立短时会话");
  expect(container.textContent).toContain("已认证，固定会话最长 5 分钟");
  expect(api.environments.discover).not.toHaveBeenCalled();
  await click("发现环境");
  expect(api.environments.discover).toHaveBeenCalledWith(
    expect.objectContaining({ projectId: pid, connectionId: cid }),
  );
  expect(container.textContent).toContain("发现 1 个环境，尚未探测");
  await click("关闭主机身份");
  expect(close).toHaveBeenCalledWith(pid, cid);
  expect(container.textContent).not.toContain("synthetic-memory-only");
});

it.each(["python", "data", "project", "dirty"] as const)(
  "App retires late local preflight on %s change",
  async (change) => {
    const mocked = bridge();
    let choiceIndex = 0;
    mocked.api.selections.pick = async (kind) => ({
      kind,
      label: `selected-${choiceIndex}`,
      selectionId: `bb3aef16-eeda-4bb7-8ced-${String(++choiceIndex).padStart(12, "0")}`,
    });
    let resolve!: (
      value: import("../electron/bridge.js").LocalPreflightResult,
    ) => void;
    const pending = new Promise<
      import("../electron/bridge.js").LocalPreflightResult
    >((done) => {
      resolve = done;
    });
    const preflight = vi.fn<DesktopAPI["local"]["preflight"]>(() => pending);
    mocked.api.local.preflight = preflight;
    await mount(mocked.api);
    await click("选择现有 Python");
    await click("选择数据目录");
    expect(preflight).not.toHaveBeenCalled();
    await click("检查本机环境与数据");
    expect(preflight).toHaveBeenCalledTimes(1);
    const input = preflight.mock.calls[0][0];
    if (change === "python") await click("选择现有 Python");
    else if (change === "data") await click("选择数据目录");
    else if (change === "dirty") await click("画布新增层");
    else {
      mocked.api.projects.importProject = async () => ({
        project: {
          ...project(),
          projectId: "bc3aef16-eeda-4bb7-8ced-58d6563fb40e",
        },
        readOnly: false,
      });
      await click("导入 JSON 工程");
    }
    await act(async () =>
      resolve({
        ...input,
        environment: { ok: true, code: "ENVIRONMENT_READY" },
        data: { ok: true, code: "DATASET_READY" },
        versions: {
          python: "late-python",
          prefix: "late",
          torch: "late-torch",
          torchvision: "late",
          matplotlib: "late",
        },
        datasetNames: ["MNIST"],
      }),
    );
    expect(container.textContent).not.toContain("late-torch");
    expect(container.textContent).not.toContain("正在检查本机环境与数据");
  },
);
