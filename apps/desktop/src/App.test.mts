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
        element(
          "output",
          { "data-testid": "visible-selected" },
          props.selectedBlock,
        ),
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
      listProfiles: async () => [],
      createProfile: unsupported,
      updateProfile: unsupported,
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
  api.connections.authenticate = vi.fn(api.connections.authenticate);
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
  api.connections.listProfiles = async () => [
    {
      targetId: "55555555-5555-4555-8555-555555555555",
      revision: 1,
      alias: "离线目标",
      endpoint: { host: "offline.invalid", port: 22 },
      username: "student",
    },
  ];
  await mount(api);
  await click("SSH 主机身份设置");
  await click("使用此服务器：离线目标");
  expect(container.textContent).toContain("不登录、不上传或运行任务");
  expect(
    container.querySelector<HTMLInputElement>(
      'section[aria-labelledby="ssh-identity-heading"] input',
    )!.value,
  ).toBe("offline.invalid");
  expect(api.connections.authenticate).not.toHaveBeenCalled();
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
  api.connections.listProfiles = async () => [
    {
      targetId: "55555555-5555-4555-8555-555555555555",
      revision: 1,
      alias: "课堂",
      endpoint: scope.endpoint,
      username: "synthetic",
    },
  ];
  await click("SSH 主机身份设置");
  await click("使用此服务器：课堂");
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

it("beginner guide navigates without execution and SSH mode hides local-only selections", async () => {
  const mocked = bridge(),
    api = mocked.api;
  api.selections.pick = vi.fn(api.selections.pick);
  api.local.preflight = vi.fn(api.local.preflight);
  api.runs.start = vi.fn(api.runs.start);
  api.connections.probe = vi.fn(api.connections.probe);
  api.connections.authenticate = vi.fn(api.connections.authenticate);
  api.connections.listProfiles = vi.fn(async () => []);
  api.environments.discover = vi.fn(api.environments.discover);
  await mount(api);
  await click("前往运行位置");
  expect(document.activeElement?.id).toBe("environment-heading");
  await act(async () => {
    const select = [...container.querySelectorAll("label")]
      .find((node) => node.textContent?.startsWith("运行位置"))!
      .querySelector("select")!;
    Object.getOwnPropertyDescriptor(
      dom.window.HTMLSelectElement.prototype,
      "value",
    )!.set!.call(select, "ssh");
    select.dispatchEvent(new dom.window.Event("change", { bubbles: true }));
  });
  expect(container.textContent).toContain("本机无需准备数据副本");
  expect(
    [...container.querySelectorAll("button")].some(
      (node) => node.textContent === "选择现有 Python",
    ),
  ).toBe(false);
  expect(
    [...container.querySelectorAll("button")].some(
      (node) => node.textContent === "选择数据目录",
    ),
  ).toBe(false);
  await click("配置服务器环境与数据");
  expect(api.connections.listProfiles).toHaveBeenCalledTimes(1);
  expect(document.activeElement?.id).toBe("server-configuration");
  for (const action of [
    api.selections.pick,
    api.local.preflight,
    api.runs.start,
    api.connections.probe,
    api.connections.authenticate,
    api.environments.discover,
    mocked.save,
  ])
    expect(action).not.toHaveBeenCalled();
  await click("前往检查与运行");
  expect(document.activeElement?.id).toBe("compile-heading");
  expect(container.textContent).toContain("先保存或选择服务器概要");
});

it.each([
  ["project", "选择目录并打开", "打开或新建工程未完成", "project-heading"],
  ["compile", "检查与编译", "检查与编译未完成", "compile-heading"],
] as const)(
  "friendly %s failure hides private text and navigates without repeating operations",
  async (stage, label, message, heading) => {
    const { api, save } = bridge();
    const secret =
      "alice@private.example /home/alice/private password=secret token=key";
    api.selections.pick = vi.fn(async (kind) => ({
      kind,
      selectionId: "selected",
      label: "selected",
    }));
    api.projects.open = vi.fn(async () => {
      throw new Error(secret);
    });
    api.projects.compile = vi.fn(async () => {
      throw new Error(secret);
    });
    api.runs.start = vi.fn(api.runs.start);
    api.connections.authenticate = vi.fn(api.connections.authenticate);
    await mount(api);
    await click(label);
    const card = container.querySelector('[role="alert"]')!;
    expect(card.textContent).toContain(message);
    expect(card.textContent).not.toContain(secret);
    const details = card.querySelector("details")!;
    expect(details.open).toBe(false);
    await act(async () => {
      details.open = true;
    });
    expect(details.textContent).not.toContain("private.example");
    await act(async () => {
      card.querySelector("button")!.click();
    });
    expect(document.activeElement?.id).toBe(heading);
    expect(
      stage === "project" ? api.projects.open : api.projects.compile,
    ).toHaveBeenCalledTimes(1);
    for (const action of [api.runs.start, api.connections.authenticate, save])
      expect(action).not.toHaveBeenCalled();
  },
);

it("uncertain start can explicitly refresh history without retrying training", async () => {
  const { api } = bridge();
  api.selections.pick = vi.fn(async (kind) => ({
    kind,
    selectionId: `${kind}-selected`,
    label: "selected",
  }));
  api.projects.compile = vi.fn(async () => ({
    revision: 1,
    programHash: "a".repeat(64),
    runnable: true,
    diagnostics: [],
  }));
  let accepted = false;
  api.runs.start = vi.fn(async () => {
    accepted = true;
    throw new Error("/home/private token=secret");
  });
  const record: import("../electron/bridge.js").Run = {
    runId: "accepted-run",
    projectId: project().projectId,
    status: "RUNNING",
    connectionState: "connected",
    syncState: "pending",
    config: {
      runId: "accepted-run",
      projectId: project().projectId,
      projectRevision: 1,
      programHash: "a".repeat(64),
      codeHash: "b".repeat(64),
      bundleHash: "c".repeat(64),
      targetId: "local",
      runner: "local",
      dataRoot: "test-data",
      runRoot: "test-run",
      pythonExecutable: "test-python",
      executionMode: "full",
      seed: 0,
      numWorkers: 0,
    },
  };
  api.runs.list = vi.fn(async () => (accepted ? [record] : []));
  await mount(api);
  await click("选择现有 Python");
  await click("选择数据目录");
  await click("检查与编译");
  await click("开始本次运行");
  const card = container.querySelector('[role="alert"]')!;
  expect(card.textContent).toContain("启动运行未确认");
  expect(card.textContent).not.toContain("secret");
  expect(container.textContent).toContain("暂无运行记录");
  await act(async () => {
    card.querySelector("button")!.click();
  });
  expect(document.activeElement?.id).toBe("history-heading");
  expect(api.runs.list).toHaveBeenCalledTimes(1);
  await click("刷新运行历史");
  expect(api.runs.list).toHaveBeenCalledTimes(2);
  expect(container.textContent).toContain("accepted");
  expect(container.textContent).toContain("RUNNING");
  expect(api.runs.start).toHaveBeenCalledTimes(1);
  expect(button("开始本次运行").disabled).toBe(true);
});

it("history refresh discards a late failure from the previous request", async () => {
  const { api } = bridge();
  api.runs.list = vi.fn(async () => []);
  api.runs.start = vi.fn(api.runs.start);
  await mount(api);
  let reject!: (reason: unknown) => void;
  const previous = new Promise<import("../electron/bridge.js").Run[]>(
    (_resolve, fail) => {
      reject = fail;
    },
  );
  vi.mocked(api.runs.list).mockImplementationOnce(() => previous);
  await click("刷新运行历史");
  await click("刷新运行历史");
  await act(async () => {
    reject(new Error("late private /home/user token=secret"));
  });
  expect(api.runs.list).toHaveBeenCalledTimes(3);
  expect(container.querySelector('[role="alert"]')).toBeNull();
  expect(container.textContent).toContain("暂无运行记录");
  expect(api.runs.start).not.toHaveBeenCalled();
});

it("successful explicit history refresh clears only its recovered read error", async () => {
  const { api } = bridge();
  api.runs.list = vi
    .fn<DesktopAPI["runs"]["list"]>()
    .mockRejectedValueOnce(new Error("private history error"))
    .mockResolvedValue([]);
  await mount(api);
  expect(container.querySelector('[role="alert"]')?.textContent).toContain(
    "读取历史未完成",
  );
  await click("刷新运行历史");
  expect(container.querySelector('[role="alert"]')).toBeNull();
  expect(api.runs.list).toHaveBeenCalledTimes(2);
});

it.each(["start", "save", "export"] as const)(
  "history failure then recovery preserves unresolved %s failure",
  async (stage) => {
    const { api, save, exported } = bridge();
    api.runs.list = vi.fn<DesktopAPI["runs"]["list"]>().mockResolvedValue([]);
    api.runs.start = vi.fn(async () => {
      // Model a lost ACK after the service could already have accepted work.
      throw new Error("private start acknowledgement lost");
    });
    save.mockRejectedValue(new Error("private save failure"));
    exported.mockRejectedValue(new Error("private export failure"));
    api.selections.pick = vi.fn(async (kind) => ({
      kind,
      selectionId: `${kind}-selected`,
      label: "selected",
    }));
    api.projects.compile = vi.fn(async () => ({
      revision: 1,
      programHash: "a".repeat(64),
      runnable: true,
      diagnostics: [],
    }));
    await mount(api);
    const message =
      stage === "start"
        ? "启动运行未确认"
        : stage === "save"
          ? "保存工程未完成"
          : "导出工程未完成";
    if (stage === "start") {
      await click("选择现有 Python");
      await click("选择数据目录");
      await click("检查与编译");
      await click("开始本次运行");
    } else if (stage === "save") {
      await click("画布新增层");
      await advance(800);
    } else await click("导出当前工程");
    expect(container.textContent).toContain(message);
    vi.mocked(api.runs.list).mockRejectedValueOnce(
      new Error("private history failure"),
    );
    await click("刷新运行历史");
    const afterFailedRefresh = container.textContent;
    await click("刷新运行历史");
    const afterSuccessfulRefresh = container.textContent;
    expect(afterSuccessfulRefresh).not.toContain("读取历史未完成");
    expect(afterSuccessfulRefresh).toContain(message);
    expect(afterFailedRefresh).toContain("读取历史未完成");
    expect(afterFailedRefresh).toContain(message);
    expect(container.textContent).not.toContain("private");
    expect(api.runs.list).toHaveBeenCalledTimes(3);
    expect(api.runs.start).toHaveBeenCalledTimes(stage === "start" ? 1 : 0);
    expect(save).toHaveBeenCalledTimes(stage === "save" ? 1 : 0);
    expect(exported).toHaveBeenCalledTimes(stage === "export" ? 1 : 0);
    if (stage === "save") {
      await advance(4000);
      expect(save).toHaveBeenCalledTimes(1);
      expect(container.textContent).toContain("自动保存已暂停");
      expect(
        container.querySelector('[data-testid="visible-blocks"]')?.textContent,
      ).toBe("1");
    }
  },
);

it("tutorial arithmetic preserves an unsaved draft and blocks native example creation", async () => {
  const h = bridge(),
    pick = vi.fn().mockResolvedValue(null),
    create = vi.fn();
  h.api.selections.pick = pick;
  h.api.projects.create = create;
  h.api.runs.start = vi.fn();
  h.api.projects.compile = vi.fn();
  await mount(h.api);
  await click("画布新增层");
  expect(container.textContent).toContain("有未保存配置");
  await click("打开离线教程");
  expect(document.activeElement?.id).toBe("tutorial-heading");
  await click("下一个窗口");
  expect(container.querySelector("output[aria-live]")?.textContent).toBe(
    "窗口求和：72",
  );
  expect(button("在新目录创建 MNIST 教学副本").disabled).toBe(true);
  await click("在新目录创建 MNIST 教学副本");
  expect(pick).not.toHaveBeenCalled();
  expect(create).not.toHaveBeenCalled();
  expect(h.api.runs.start).not.toHaveBeenCalled();
  expect(h.api.projects.compile).not.toHaveBeenCalled();
  expect(
    container.querySelector('[data-testid="visible-blocks"]')?.textContent,
  ).toBe("1");
  expect(h.save).not.toHaveBeenCalled();
  await advance(800);
  expect(h.save).toHaveBeenCalledTimes(1);
  expect(h.save.mock.calls[0][0].workspaces.model.blocks.blocks).toHaveLength(
    1,
  );
});
it("tutorial example selection cancellation keeps the current project and invokes no create", async () => {
  const h = bridge(),
    pick = vi.fn().mockResolvedValue(null),
    create = vi.fn();
  h.api.selections.pick = pick;
  h.api.projects.create = create;
  await mount(h.api);
  await click("打开离线教程");
  await click("在新目录创建 MNIST 教学副本");
  expect(pick).toHaveBeenCalledExactlyOnceWith("project");
  expect(create).not.toHaveBeenCalled();
  expect(container.textContent).toContain("真实组件测试工程");
  expect(h.save).not.toHaveBeenCalled();
});
it("offline tutorial entry to arithmetic to real Python block/code mapping and new example leaves original bytes untouched", async () => {
  const directory = await mkdtemp(join(tmpdir(), "easyai-tutorial-vertical-")),
    originalRoot = join(directory, "original"),
    copyRoot = join(directory, "copy");
  await mkdir(originalRoot);
  await mkdir(copyRoot);
  const original = await readFile(
    new URL("../../../packages/contracts/fixtures/mnist.json", import.meta.url),
  );
  await writeFile(join(originalRoot, "project.easyai.json"), original);
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
  let nativeDirectory = originalRoot;
  const workflow = new MainWorkflow(
    () => backend,
    async () => nativeDirectory,
    () => {},
  );
  vi.stubGlobal(
    "ResizeObserver",
    class {
      observe() {}
      disconnect() {}
    },
  );
  try {
    const selection = (await workflow.invoke("easyai:selections:pick", [
      "project",
    ])) as SelectionResult;
    await workflow.invoke("easyai:projects:open", [selection.selectionId]);
    const h = bridge();
    h.api.projects.current = async () =>
      (await workflow.invoke("easyai:projects:current", [])) as ProjectSession;
    h.api.projects.compile = vi.fn(
      async (project, requestId) =>
        (await workflow.invoke("easyai:projects:compile", [
          project,
          requestId,
        ])) as Awaited<ReturnType<DesktopAPI["projects"]["compile"]>>,
    );
    h.api.selections.pick = vi.fn(
      async (kind) =>
        (await workflow.invoke("easyai:selections:pick", [
          kind,
        ])) as SelectionResult,
    );
    h.api.projects.create = vi.fn(
      async (...args) =>
        (await workflow.invoke(
          "easyai:projects:create",
          args,
        )) as ProjectSession,
    );
    h.api.runs.start = vi.fn();
    await mount(h.api);
    await click("打开离线教程");
    await click("下一个窗口");
    expect(container.querySelector("output[aria-live]")?.textContent).toBe(
      "窗口求和：72",
    );
    expect(button("显示对应代码").disabled).toBe(true);
    await click("检查与编译");
    await act(async () => {
      const result = await vi.mocked(h.api.projects.compile).mock.results[0]
        .value;
      expect(result.runnable).toBe(true);
    });
    expect(button("显示对应代码").disabled).toBe(false);
    await click("定位关联积木");
    expect(
      container.querySelector('[data-testid="visible-tab"]')?.textContent,
    ).toBe("model");
    const selected = container.querySelector(
      '[data-testid="visible-selected"]',
    )?.textContent;
    expect(selected).toBeTruthy();
    await click("显示对应代码");
    expect(
      container.querySelector(
        '[aria-label="教程关联的只读生成代码"] .code-selected',
      )?.textContent,
    ).toContain("nn.Conv2d");
    expect(h.api.projects.compile).toHaveBeenCalledTimes(1);
    await advance(2400);
    expect(h.save).not.toHaveBeenCalled();
    expect(h.dirty.mock.calls.every(([value]) => value === false)).toBe(true);
    expect(await readFile(join(originalRoot, "project.easyai.json"))).toEqual(
      original,
    );
    nativeDirectory = copyRoot;
    await click("在新目录创建 MNIST 教学副本");
    await act(async () => {
      await vi.mocked(h.api.selections.pick).mock.results[0].value;
      await vi.mocked(h.api.projects.create).mock.results[0].value;
    });
    const copied = JSON.parse(
      await readFile(join(copyRoot, "project.easyai.json"), "utf8"),
    );
    expect(copied.projectId).not.toBe(
      JSON.parse(original.toString()).projectId,
    );
    expect(copied.workspaces.model.blocks.blocks.length).toBeGreaterThan(0);
    expect(await readFile(join(originalRoot, "project.easyai.json"))).toEqual(
      original,
    );
    expect(h.api.runs.start).not.toHaveBeenCalled();
    expect(
      container.querySelector('[aria-label="教程关联的只读生成代码"]'),
    ).toBeNull();
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

it("tutorial example creation waits for startup project restoration to settle", async () => {
  const h = bridge();
  let restore!: (value: ProjectSession) => void;
  h.api.projects.current = () =>
    new Promise((done) => {
      restore = done;
    });
  const pick = vi.fn().mockResolvedValue(null);
  h.api.selections.pick = pick;
  const { createRoot } = await import("react-dom/client");
  root = createRoot(container);
  await act(async () => {
    root!.render(createElement(App, { api: h.api }));
  });
  await click("打开离线教程");
  expect(button("在新目录创建 MNIST 教学副本").disabled).toBe(true);
  await click("在新目录创建 MNIST 教学副本");
  expect(pick).not.toHaveBeenCalled();
  await act(async () => restore({ project: project(), readOnly: false }));
  expect(button("在新目录创建 MNIST 教学副本").disabled).toBe(false);
});

it("package planning entry stays read-only and hiding it preserves the opened panel", async () => {
  const h = bridge();
  const raw = JSON.parse(
    await readFile(
      new URL("../../../packages/package-groups/catalog.json", import.meta.url),
      "utf8",
    ),
  );
  const catalog = vi.fn<NonNullable<DesktopAPI["packages"]>["catalog"]>(
    async () => ({
      catalogVersion: 1,
      packages: raw.packages.map((item: object) => ({
        ...item,
        targetVersion: null,
      })),
      profiles: ["teacher-existing", "easyai-cpu"],
      executionEnabled: false,
    }),
  );
  const plan = vi.fn(),
    confirm = vi.fn();
  h.api.packages = { catalog, plan, confirm, job: vi.fn(), cancel: vi.fn() };
  await mount(h.api);
  expect(catalog).not.toHaveBeenCalled();
  await click("打开包安装计划");
  expect(document.activeElement?.id).toBe("packages-heading");
  expect(catalog).toHaveBeenCalledTimes(1);
  await click("收起包安装计划");
  await click("打开包安装计划");
  expect(catalog).toHaveBeenCalledTimes(1);
  await advance(2400);
  expect(h.save).not.toHaveBeenCalled();
  expect(plan).not.toHaveBeenCalled();
  expect(confirm).not.toHaveBeenCalled();
  expect(h.dirty.mock.calls.every(([value]) => value === false)).toBe(true);
});
