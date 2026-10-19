import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { act, createElement } from "react";
import type { Root } from "react-dom/client";
import { createRequire } from "node:module";
import { readFileSync } from "node:fs";
import { mkdtemp, access, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { fileURLToPath } from "node:url";
import { PackageManager } from "./PackageManager.js";
import { startBackend } from "../electron/backend.mjs";
import { MainWorkflow } from "../electron/workflow.mjs";
import type {
  DesktopAPI,
  AuthenticatedConnection,
  InstallJob,
  InstallPlan,
  PackageCatalog,
  InstallSourcePreview,
} from "../electron/bridge.js";
const require = createRequire(import.meta.url),
  { JSDOM } = require(
    require.resolve("jsdom", { paths: [require.resolve("blockly/core")] }),
  );
type API = NonNullable<DesktopAPI["packages"]>;
const planId = "d6851d61-92e8-4909-b02b-2313f1fd585d",
  environmentId = "e6851d61-92e8-4909-b02b-2313f1fd585d",
  jobId = "f6851d61-92e8-4909-b02b-2313f1fd585d";
function plan(): InstallPlan {
  return {
    planId,
    planHash: "a".repeat(64),
    targetId: "local",
    profileId: "easyai-cpu",
    environmentId,
    environmentName: "classroom",
    newEnvironment: true,
    baselineFingerprint: "b".repeat(64),
    constraintsHash: "c".repeat(64),
    packageChanges: [
      {
        packageId: "torch",
        previousVersion: null,
        targetVersion: "2.10.0+cpu",
        action: "add",
        requested: true,
      },
    ],
    requiresNetwork: true,
    downloadBytes: null,
    installedBytes: null,
    sizeStatus: "unresolved",
    platform: "linux-x86_64-cp311",
    blockers: [],
    executionEnabled: false,
  };
}
function job(): InstallJob {
  return {
    jobId,
    planId,
    planHash: plan().planHash,
    environmentId,
    state: "AWAITING_EXECUTION",
    statusCode: "INSTALL_EXECUTION_NOT_ENABLED",
    logs: ["PLAN_CONFIRMED", "INSTALL_EXECUTION_NOT_ENABLED"],
    needsReprobe: true,
    changesPossible: false,
    verified: false,
    executionEnabled: false,
  };
}
function sourcePreview(): InstallSourcePreview {
  return {
    previewId: planId,
    previewHash: "e".repeat(64),
    packageIds: ["torch", "torchvision", "matplotlib"],
    sourceName: "operator.json",
    manifestSha256: "f".repeat(64),
    launcher: { name: "python", sha256: "1".repeat(64), bytes: 1024 },
    moduleName: "conda-modules",
    moduleTreeSha256: "2".repeat(64),
    bootstrap: [{ name: "python.conda", sha256: "3".repeat(64), bytes: 2048 }],
    wheels: [{ name: "torch.whl", sha256: "4".repeat(64), bytes: 4096 }],
    sourceBytes: 6144,
    installedBytes: null,
    diskBudgetBytes: 1048576,
    executionSeconds: 60,
    authorizationExpires: "2026-10-18T23:00:00Z",
    declaredExecutionAuthorized: true,
    executionEnabled: false,
    expiresAt: "2026-10-18T12:01:00Z",
  };
}
function setup() {
  const raw = JSON.parse(
    readFileSync(
      new URL("../../../packages/package-groups/catalog.json", import.meta.url),
      "utf8",
    ),
  );
  const catalog: PackageCatalog = {
    catalogVersion: 1,
    packages: raw.packages.map((item: object) => ({
      ...item,
      targetVersion: null,
      installedVersion: null,
      installedStatus: "unknown",
    })),
    profiles: ["teacher-existing", "easyai-cpu"],
    executionEnabled: false,
  };
  const api = {
    history: vi.fn<API["history"]>(async () => ({ entries: [], limit: 64 })),
    report: vi.fn<API["report"]>(),
    chooseSources: vi.fn<API["chooseSources"]>(async () => null),
    confirmSources: vi.fn<API["confirmSources"]>(),
    catalog: vi.fn<API["catalog"]>(async () => catalog),
    plan: vi.fn<API["plan"]>(async () => plan()),
    confirm: vi.fn<API["confirm"]>(async () => job()),
    job: vi.fn<API["job"]>(async () => job()),
    cancel: vi.fn<API["cancel"]>(async () => ({
      ...job(),
      state: "CANCELLED" as const,
    })),
  } satisfies API;
  return { api, catalog };
}
let dom: InstanceType<typeof JSDOM>,
  root: Root | undefined,
  container: HTMLDivElement;
async function mount(api: API, remoteSession?: AuthenticatedConnection | null) {
  const { createRoot } = await import("react-dom/client");
  root ??= createRoot(container);
  await act(async () => {
    root!.render(createElement(PackageManager, { api, remoteSession }));
  });
}
function button(label: string) {
  const node = [...container.querySelectorAll("button")].find(
    (item) => item.textContent === label,
  );
  if (!node) throw Error("Missing button " + label);
  return node;
}
async function click(label: string) {
  await act(async () => button(label).click());
}
async function checkbox(label: string) {
  const node = [...container.querySelectorAll("label")]
    .find((item) => item.textContent?.includes(label))
    ?.querySelector<HTMLInputElement>('input[type="checkbox"]');
  if (!node) throw Error("Missing checkbox " + label);
  await act(async () => node.click());
}
async function choose(value: string) {
  const node = container.querySelector<HTMLSelectElement>(
    'select[aria-label="环境方案"]',
  )!;
  await act(async () => {
    Object.getOwnPropertyDescriptor(
      dom.window.HTMLSelectElement.prototype,
      "value",
    )!.set!.call(node, value);
    node.dispatchEvent(new dom.window.Event("change", { bubbles: true }));
  });
}
beforeEach(() => {
  dom = new JSDOM("<!doctype html><html><body></body></html>", {
    url: "https://packages.test",
  });
  for (const key of [
    "window",
    "document",
    "navigator",
    "HTMLElement",
    "Node",
    "HTMLInputElement",
    "HTMLSelectElement",
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
  container = document.createElement("div");
  document.body.append(container);
});
afterEach(async () => {
  if (root) await act(async () => root!.unmount());
  root = undefined;
  vi.unstubAllGlobals();
  dom.window.close();
});
it("catalog is read-only; group and single selections share the explicit planner", async () => {
  const h = setup();
  await mount(h.api);
  expect(container.querySelectorAll("details")).toHaveLength(4);
  expect(container.textContent).toContain("真实安装执行");
  expect(h.api.plan).not.toHaveBeenCalled();
  expect(h.api.confirm).not.toHaveBeenCalled();
  await checkbox("选择整组机器学习");
  await click("只生成安装计划");
  const request = h.api.plan.mock.calls[0][0];
  expect(new Set(request.packageIds)).toEqual(
    new Set([
      "torch",
      "torchvision",
      "matplotlib",
      "numpy",
      "scipy",
      "pandas",
      "scikit-learn",
    ]),
  );
  expect(request).toMatchObject({
    targetId: "local",
    newEnvironmentSpec: { name: "easyai-classroom" },
  });
  expect(container.textContent).toContain("未知 / 待解析");
  expect(h.api.confirm).not.toHaveBeenCalled();
  await choose("teacher-existing");
  expect(button("只生成安装计划").disabled).toBe(true);
  expect(container.textContent).toContain("教师现有环境只读");
  expect(container.querySelector('[aria-label="安装计划预览"]')).toBeNull();
});
it("only explicit reviewed consent confirms the exact plan, and cancel is a separate action", async () => {
  const h = setup();
  await mount(h.api);
  await click("只生成安装计划");
  expect(button("确认计划并登记任务").disabled).toBe(true);
  expect(h.api.confirm).not.toHaveBeenCalled();
  await checkbox("我已核对目标");
  await click("确认计划并登记任务");
  expect(h.api.confirm).toHaveBeenCalledExactlyOnceWith({
    planId,
    planHash: plan().planHash,
    confirmed: true,
    networkAcknowledged: true,
  });
  expect(
    container.querySelector('[aria-label="安装任务登记"]')?.textContent,
  ).toContain("等待执行");
  expect(container.textContent).toContain("尚未执行安装变更");
  expect(h.api.cancel).not.toHaveBeenCalled();
  await click("取消登记或请求停止");
  expect(h.api.cancel).toHaveBeenCalledExactlyOnceWith(jobId);
  expect(
    container.querySelector('[aria-label="安装任务登记"]')?.textContent,
  ).toContain("不代表环境健康");
});
it("unresolved dependencies block confirmation and any form change invalidates the old plan", async () => {
  const h = setup();
  h.api.plan.mockResolvedValue({
    ...plan(),
    blockers: ["INSTALL_DEPENDENCIES_UNRESOLVED"],
  });
  await mount(h.api);
  await click("只生成安装计划");
  expect(button("确认计划并登记任务").disabled).toBe(true);
  expect(container.querySelector('[role="alert"]')?.textContent).toContain(
    "计划被阻止",
  );
  await click("选择 MNIST 最小依赖");
  expect(container.querySelector('[aria-label="安装计划预览"]')).toBeNull();
  expect(h.api.confirm).not.toHaveBeenCalled();
});
it("failed confirmation hides private exception text and does not retry automatically", async () => {
  const h = setup();
  h.api.confirm.mockRejectedValue(
    new Error("password=private-secret /teacher"),
  );
  await mount(h.api);
  await click("只生成安装计划");
  await checkbox("我已核对目标");
  await click("确认计划并登记任务");
  expect(h.api.confirm).toHaveBeenCalledTimes(1);
  expect(container.querySelector('[role="alert"]')?.textContent).toContain(
    "同一计划",
  );
  expect(container.textContent).not.toContain("private-secret");
  await click("确认计划并登记任务");
  expect(h.api.confirm).toHaveBeenCalledTimes(2);
  expect(h.api.confirm.mock.calls[0]).toEqual(h.api.confirm.mock.calls[1]);
});
it("mismatched job identity is rejected and a pending confirmation cannot be duplicated", async () => {
  const h = setup();
  let release!: (value: InstallJob) => void;
  h.api.confirm.mockImplementation(
    () =>
      new Promise((done) => {
        release = done;
      }),
  );
  await mount(h.api);
  await click("只生成安装计划");
  await checkbox("我已核对目标");
  await click("确认计划并登记任务");
  await click("确认计划并登记任务");
  expect(h.api.confirm).toHaveBeenCalledTimes(1);
  await act(async () => release({ ...job(), environmentId: planId }));
  expect(container.querySelector('[aria-label="安装任务登记"]')).toBeNull();
  expect(container.querySelector('[role="alert"]')).not.toBeNull();
});
it("running cancellation remains unconfirmed until a separate refresh confirms it", async () => {
  const h = setup();
  h.api.cancel.mockResolvedValue({
    ...job(),
    state: "CANCEL_REQUESTED",
    changesPossible: true,
    logs: ["private-secret /teacher"],
  } as InstallJob);
  await mount(h.api);
  await click("只生成安装计划");
  await checkbox("我已核对目标");
  await click("确认计划并登记任务");
  await click("取消登记或请求停止");
  expect(
    container.querySelector('[aria-label="安装任务登记"]')?.textContent,
  ).toContain("尚未确认停止");
  expect(container.textContent).not.toContain("private-secret");
  h.api.job.mockResolvedValue({ ...job(), state: "CANCELLED" });
  await click("刷新安装任务");
  expect(
    container.querySelector('[aria-label="安装任务登记"]')?.textContent,
  ).toContain("不代表环境健康");
});
it("actual Main and authenticated sidecar generate and confirm/cancel without creating a training environment", async () => {
  const rootPath = await mkdtemp(join(tmpdir(), "easyai-install-ui-"));
  const cwd = fileURLToPath(
      new URL("../../../services/backend/", import.meta.url),
    ),
    storage = join(rootPath, "state");
  const backend = await startBackend(
    join(
      cwd,
      process.platform === "win32"
        ? ".venv/Scripts/python.exe"
        : ".venv/bin/python",
    ),
    cwd,
    10000,
    storage,
  );
  const workflow = new MainWorkflow(() => backend, vi.fn(), vi.fn());
  const api = {
    chooseSources: vi.fn<API["chooseSources"]>(async () => null),
    confirmSources: vi.fn<API["confirmSources"]>(),
    history: vi.fn<API["history"]>(async () => ({ entries: [], limit: 64 })),
    report: vi.fn<API["report"]>(),
    catalog: vi.fn(
      async () =>
        (await workflow.invoke(
          "easyai:packages:catalog",
          [],
        )) as PackageCatalog,
    ),
    plan: vi.fn(
      async (request: Parameters<API["plan"]>[0]) =>
        (await workflow.invoke("easyai:packages:plan", [
          request,
        ])) as InstallPlan,
    ),
    confirm: vi.fn(
      async (request: Parameters<API["confirm"]>[0]) =>
        (await workflow.invoke("easyai:installJobs:confirm", [
          request,
        ])) as InstallJob,
    ),
    job: async (id: string) =>
      (await workflow.invoke("easyai:installJobs:get", [id])) as InstallJob,
    cancel: vi.fn(
      async (id: string) =>
        (await workflow.invoke("easyai:installJobs:cancel", [
          id,
        ])) as InstallJob,
    ),
  } satisfies API;
  try {
    await mount(api);
    await act(async () => {
      await api.catalog.mock.results[0].value;
    });
    await click("只生成安装计划");
    await act(async () => {
      await api.plan.mock.results[0].value;
    });
    const generated = await api.plan.mock.results[0].value;
    if (process.platform !== "linux" || process.arch !== "x64") {
      expect(generated.blockers).toEqual([
        "INSTALL_PROFILE_PLATFORM_UNSUPPORTED",
      ]);
      expect(button("确认计划并登记任务").disabled).toBe(true);
    } else {
      expect(generated.blockers).toEqual([]);
      expect(generated.sizeStatus).toBe("locked-wheel-estimate");
      await checkbox("我已核对目标");
      await click("确认计划并登记任务");
      await act(async () => {
        await api.confirm.mock.results[0].value;
      });
      const registered = await api.confirm.mock.results[0].value;
      expect(registered.state).toBe("AWAITING_EXECUTION");
      expect(registered.executionEnabled).toBe(false);
      await click("取消登记或请求停止");
      await act(async () => {
        await api.cancel.mock.results[0].value;
      });
      expect(
        container.querySelector('[aria-label="安装任务登记"]')?.textContent,
      ).toContain("不代表环境健康");
    }
    await expect(
      access(join(storage, "training-environments")),
    ).rejects.toMatchObject({ code: "ENOENT" });
  } finally {
    if (root) {
      await act(async () => root!.unmount());
      root = undefined;
    }
    workflow.dispose();
    await backend.stop();
    await rm(rootPath, { recursive: true, force: true });
  }
}, 20000);

it("an enabled host still requires the exact plan and a fresh explicit install confirmation", async () => {
  const h = setup();
  h.catalog.executionEnabled = true;
  h.api.plan.mockResolvedValue({
    ...plan(),
    executionEnabled: true,
    requiresNetwork: false,
    runtimeFingerprint: "d".repeat(64),
    bootstrapBytes: 100,
    diskBudgetBytes: 1000,
  });
  await mount(h.api);
  await click("只生成安装计划");
  expect(container.textContent).toContain("本次来源已在本机，不下载依赖");
  expect(button("确认计划并执行受控安装").disabled).toBe(true);
  expect(h.api.confirm).not.toHaveBeenCalled();
  await checkbox("我已核对目标、来源");
  await click("确认计划并执行受控安装");
  expect(h.api.confirm).toHaveBeenCalledTimes(1);
  expect(h.api.confirm).toHaveBeenLastCalledWith({
    planId,
    planHash: plan().planHash,
    confirmed: true,
    networkAcknowledged: true,
  });
});

it("native source preview shows checked files and budgets, needs fresh explicit registration, then invalidates the old plan", async () => {
  const h = setup(),
    preview = sourcePreview();
  h.api.chooseSources.mockResolvedValue(preview);
  h.api.confirmSources.mockResolvedValue({
    previewId: preview.previewId,
    manifestSha256: preview.manifestSha256,
    runtimeFingerprint: "9".repeat(64),
    executionEnabled: false,
    authorizationExpires: preview.authorizationExpires,
  });
  await mount(h.api);
  await click("只生成安装计划");
  await click("选择本地离线来源");
  expect(h.api.chooseSources).toHaveBeenCalledWith({
    packageIds: ["torch", "torchvision", "matplotlib"],
  });
  expect(container.textContent).toContain("operator.json");
  expect(container.textContent).toContain(preview.launcher.sha256);
  expect(container.textContent).toContain("实际解包占用未知");
  expect(button("确认登记本地来源").disabled).toBe(true);
  expect(h.api.confirmSources).not.toHaveBeenCalled();
  await checkbox("我已确认来源来自可信操作者");
  await click("确认登记本地来源");
  expect(h.api.confirmSources).toHaveBeenCalledWith({
    previewId: preview.previewId,
    previewHash: preview.previewHash,
    confirmed: true,
  });
  expect(container.textContent).toContain("本地来源已登记，执行授权仍关闭");
  expect(container.querySelector('[aria-label="来源核验预览"]')).toBeNull();
  expect(h.api.confirm).not.toHaveBeenCalled();
  expect(h.api.plan).toHaveBeenCalledTimes(1);
});

it("native cancellation preserves the existing plan and source errors cannot expose paths or authorize execution", async () => {
  const h = setup();
  await mount(h.api);
  await click("只生成安装计划");
  const previous = container.textContent;
  await click("选择本地离线来源");
  expect(container.textContent).toBe(previous);
  expect(h.api.confirmSources).not.toHaveBeenCalled();
  h.api.chooseSources.mockRejectedValue(
    Error("private source path must not leak"),
  );
  await click("选择本地离线来源");
  expect(container.textContent).toContain("来源校验未完成");
  expect(container.textContent).not.toContain("private source path");
  expect(container.querySelector('input[type="file"]')).toBeNull();
  expect(h.api.confirm).not.toHaveBeenCalled();
});

it("saved result, failure and unknown tasks can be reopened from the normal panel without knowing an ID or restarting work", async () => {
  const h = setup();
  type Summary = Awaited<ReturnType<API["history"]>>["entries"][number];
  const summary = (
    id: string,
    state: InstallJob["state"],
    observation: Summary["observation"],
  ): Summary => ({
    jobId: id,
    environmentId,
    planId,
    planHash: plan().planHash,
    recordedAt: "2026-10-18T10:00:00Z",
    recordedState: state,
    state,
    statusCode:
      state === "SUCCEEDED" ? "INSTALL_VERIFIED" : "INSTALL_STOP_UNCONFIRMED",
    origin: "recovered",
    workerAlive: false,
    observation,
  });
  const success = summary(jobId, "SUCCEEDED", "historical"),
    failed = summary(environmentId, "FAILED", "historical"),
    unknown = summary(planId, "CANCEL_REQUESTED", "stop-unconfirmed");
  h.api.history.mockResolvedValue({
    entries: [success, failed, unknown],
    limit: 64,
  });
  h.api.report.mockImplementation(async (id) => {
    const value = [success, failed, unknown].find(
      (entry) => entry.jobId === id,
    )!;
    const record = {
      ...job(),
      jobId: id,
      state: value.state,
      verified: value.state === "SUCCEEDED",
      needsReprobe: value.state !== "SUCCEEDED",
    };
    return {
      summary: value,
      recorded: record,
      observed: record,
      currentEnvironmentVerified: false,
    };
  });
  await mount(h.api);
  expect(container.textContent).toContain("已保存安装任务与报告");
  expect(container.textContent).toContain("历史结果记录");
  expect(container.textContent).toContain("停止未确认");
  const select = async (id: string) => {
    await act(async () =>
      container
        .querySelector<HTMLButtonElement>(
          `button[aria-label="查看安装报告 ${id}"]`,
        )!
        .click(),
    );
  };
  await select(success.jobId);
  expect(container.textContent).toContain("账本记载当时已通过复检");
  expect(container.textContent).toContain("不能据此启动训练");
  await select(failed.jobId);
  expect(
    container.querySelector('[aria-label="已保存安装报告"]')?.textContent,
  ).toContain("任务失败，需要重新检查");
  await select(unknown.jobId);
  expect(
    container.querySelector('[aria-label="已保存安装报告"]')?.textContent,
  ).toContain("停止未确认");
  await click("刷新已保存安装任务");
  await click("重新读取此报告");
  expect(h.api.plan).not.toHaveBeenCalled();
  expect(h.api.confirm).not.toHaveBeenCalled();
  expect(h.api.cancel).not.toHaveBeenCalled();
  expect(h.api.confirmSources).not.toHaveBeenCalled();
});

it("recovered awaiting confirmation is read-only expiry, not a new actionable install job", async () => {
  const h = setup();
  const record = job();
  const observed = {
    ...record,
    state: "CANCELLED" as const,
    statusCode: "INSTALL_RESTART_CONFIRMATION_EXPIRED",
  };
  const summary = {
    jobId,
    environmentId,
    planId,
    planHash: plan().planHash,
    recordedAt: "2026-10-18T10:00:00Z",
    recordedState: record.state,
    state: observed.state,
    statusCode: observed.statusCode,
    origin: "recovered" as const,
    workerAlive: false,
    observation: "historical" as const,
  };
  h.api.history.mockResolvedValue({ entries: [summary], limit: 64 });
  h.api.report.mockResolvedValue({
    summary,
    recorded: record,
    observed,
    currentEnvironmentVerified: false,
  });
  await mount(h.api);
  await act(async () =>
    container
      .querySelector<HTMLButtonElement>(
        `button[aria-label="查看安装报告 ${jobId}"]`,
      )!
      .click(),
  );
  expect(container.textContent).toContain("旧等待确认已失效");
  expect(container.querySelector('[aria-label="安装任务登记"]')).toBeNull();
  expect(h.api.confirm).not.toHaveBeenCalled();
  expect(h.api.cancel).not.toHaveBeenCalled();
});

it("remote plans bind the authenticated saved target and never use local source registration", async () => {
  const h = setup();
  const auth: AuthenticatedConnection = {
    targetId: planId,
    targetRevision: 1,
    projectId: environmentId,
    requestId: jobId,
    identityRequestId: planId,
    username: "synthetic",
    authenticated: true,
    method: "password",
    expiresInSeconds: 300,
    scope: {
      projectId: environmentId,
      connectionId: jobId,
      endpoint: { host: "synthetic.invalid", port: 22 },
      hostFingerprint: "SHA256:" + "A".repeat(43),
    },
  };
  h.api.plan.mockResolvedValue({
    ...plan(),
    targetId: planId,
    targetIdentity: {
      projectId: environmentId,
      targetId: planId,
      targetRevision: 1,
      endpoint: auth.scope.endpoint,
      hostFingerprint: auth.scope.hostFingerprint,
      username: auth.username,
      root: "/synthetic/owned",
    },
    remoteFreeBytes: 1048576,
  });
  await mount(h.api, auth);
  const target = container.querySelector<HTMLSelectElement>(
    'select[aria-label="安装目标"]',
  )!;
  await act(async () => {
    Object.getOwnPropertyDescriptor(
      dom.window.HTMLSelectElement.prototype,
      "value",
    )!.set!.call(target, "remote");
    target.dispatchEvent(new dom.window.Event("change", { bubbles: true }));
  });
  expect(button("选择本地离线来源").disabled).toBe(true);
  await click("只生成安装计划");
  expect(h.api.plan.mock.calls[0][0]).toMatchObject({
    targetId: planId,
    remoteSession: { projectId: environmentId, connectionId: jobId },
  });
  expect(container.textContent).toContain("/synthetic/owned");
  expect(h.api.chooseSources).not.toHaveBeenCalled();
  expect(h.api.confirm).not.toHaveBeenCalled();
});
