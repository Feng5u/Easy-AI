import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { act, createElement } from "react";
import { createRequire } from "node:module";
import type { Root } from "react-dom/client";
import { AuthenticatedPanel } from "./AuthenticatedPanel.js";
import type {
  AuthenticatedConnection,
  DesktopAPI,
  EnvironmentCatalog,
  EnvironmentProbeResult,
  RemoteRunControls,
  RemoteBinding,
} from "../electron/bridge.js";
const require = createRequire(import.meta.url);
const { JSDOM } = require(
  require.resolve("jsdom", { paths: [require.resolve("blockly/core")] }),
);
const projectId = "11111111-1111-4111-8111-111111111111",
  identityRequestId = "22222222-2222-4222-8222-222222222222",
  connectionId = "33333333-3333-4333-8333-333333333333",
  envId = "44444444-4444-4444-8444-444444444444";
let root: Root | undefined,
  dom: InstanceType<typeof JSDOM>,
  container: HTMLDivElement;
function deferred<T>() {
  let resolve!: (value: T) => void;
  const promise = new Promise<T>((r) => {
    resolve = r;
  });
  return { promise, resolve };
}
function setup() {
  const info: AuthenticatedConnection = {
    projectId,
    requestId: envId,
    identityRequestId,
    scope: {
      projectId,
      connectionId,
      endpoint: { host: "synthetic.invalid", port: 22 },
      hostFingerprint: "SHA256:" + "A".repeat(43),
    },
    username: "synthetic",
    authenticated: true,
    method: "password",
    expiresInSeconds: 300,
  };
  const api: DesktopAPI["connections"] = {
    probe: vi.fn(),
    confirm: vi.fn(),
    cancel: vi.fn(async () => {}),
    authenticate: vi.fn(async (_pid, rid) => ({ ...info, requestId: rid })),
    cancelAuth: vi.fn(async () => {}),
    close: vi.fn(async () => {}),
    current: vi.fn(async () => info),
  };
  const catalog: EnvironmentCatalog = {
    projectId,
    connectionId,
    requestId: envId,
    scope: info.scope,
    environments: [
      {
        environmentId: envId,
        kind: "python",
        location: "/synthetic/python",
        readOnly: true,
      },
    ],
    note: "unprobed",
  };
  const report: EnvironmentProbeResult = {
    projectId,
    connectionId,
    requestId: envId,
    scope: info.scope,
    environmentId: envId,
    environmentReady: false,
    dataReady: null,
    issues: [
      { code: "TORCH_IMPORT_FAILED", suggestion: "synthetic test fixture" },
    ],
    report: {
      schemaVersion: 1,
      nonce: envId,
      platform: "linux",
      python: {
        executable: "/synthetic/python",
        prefix: "/synthetic",
        version: [3, 11, 1],
      },
      imports: {
        torch: { version: null, imported: false, error: "missing" },
        torchvision: { version: null, imported: false, error: "missing" },
        matplotlib: { version: null, imported: false, error: "missing" },
      },
      devices: { cudaAvailable: null, mpsAvailable: null },
      tensor: {
        attempted: false,
        ok: false,
        device: "cpu",
        error: "dependency_missing",
      },
      dataset: null,
    },
  };
  const environments: DesktopAPI["environments"] = {
    discover: vi.fn(async () => catalog),
    probe: vi.fn(async () => report),
    cancel: vi.fn(async () => {}),
  };
  const invalidated = vi.fn();
  return { api, environments, info, catalog, report, invalidated };
}
async function mount(s: ReturnType<typeof setup>, remote?: RemoteRunControls) {
  const { createRoot } = await import("react-dom/client");
  root ??= createRoot(container);
  await act(async () =>
    root!.render(
      createElement(AuthenticatedPanel, {
        api: s.api,
        environments: s.environments,
        projectId,
        identityRequestId,
        onInvalidated: s.invalidated,
        remote,
      }),
    ),
  );
}
async function input(label: string, value: string) {
  await act(async () => {
    const element = [...container.querySelectorAll("label")]
      .find((e) => e.textContent?.startsWith(label))!
      .querySelector("input,select")!;
    Object.getOwnPropertyDescriptor(
      element.tagName === "SELECT"
        ? dom.window.HTMLSelectElement.prototype
        : dom.window.HTMLInputElement.prototype,
      "value",
    )!.set!.call(element, value);
    element.dispatchEvent(
      new dom.window.Event(element.tagName === "SELECT" ? "change" : "input", {
        bubbles: true,
      }),
    );
  });
}
async function click(label: string) {
  await act(async () => {
    const button = [...container.querySelectorAll("button")].find(
      (e) => e.textContent === label,
    );
    if (!button) throw new Error(label);
    button.click();
  });
}
async function credentials() {
  await input("SSH 用户名", "synthetic");
  await input("SSH 密码", "synthetic-memory-only");
}
beforeEach(() => {
  dom = new JSDOM("<!doctype html><html><body></body></html>", {
    url: "https://synthetic.test/",
  });
  for (const key of [
    "window",
    "document",
    "navigator",
    "HTMLElement",
    "HTMLInputElement",
    "Event",
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
  container = dom.window.document.createElement("div");
  dom.window.document.body.append(container);
});
afterEach(async () => {
  if (root) await act(async () => root!.unmount());
  root = undefined;
  vi.useRealTimers();
  vi.unstubAllGlobals();
  dom.window.close();
});
it("password is uncontrolled and cleared synchronously before auth awaits; failed SDK text stays hidden", async () => {
  const s = setup(),
    delayed = deferred<AuthenticatedConnection>();
  vi.mocked(s.api.authenticate).mockImplementation(() => delayed.promise);
  await mount(s);
  await credentials();
  await click("认证并建立短时会话");
  expect(
    container.querySelector<HTMLInputElement>('input[type="password"]')!.value,
  ).toBe("");
  expect(container.textContent).not.toContain("synthetic-memory-only");
  await act(async () => {
    await click("关闭认证会话");
    delayed.resolve(s.info);
  });
  expect(s.api.cancelAuth).toHaveBeenCalled();
  expect(s.invalidated).toHaveBeenCalled();
  expect(container.textContent).not.toContain("已认证，固定会话");
});
it("authenticated normal controls discover then explicitly probe, defaults CPU and no dataset", async () => {
  const s = setup();
  await mount(s);
  await credentials();
  await click("认证并建立短时会话");
  expect(container.textContent).toContain("已认证，固定会话最长 5 分钟");
  expect(s.environments.discover).not.toHaveBeenCalled();
  await input("发现方式", "python");
  await input("远端可执行文件绝对路径", "/synthetic/python");
  await click("发现环境");
  expect(s.environments.discover).toHaveBeenCalledWith(
    expect.objectContaining({
      projectId,
      connectionId,
      pythonPath: "/synthetic/python",
    }),
  );
  expect(container.textContent).toContain("尚未探测");
  expect(s.environments.probe).not.toHaveBeenCalled();
  await click("只读检查所选环境");
  expect(s.environments.probe).toHaveBeenCalledWith(
    expect.objectContaining({ environmentId: envId, device: "cpu" }),
  );
  expect(
    vi.mocked(s.environments.probe).mock.calls[0][0].dataset,
  ).toBeUndefined();
  expect(container.textContent).toContain("环境：未就绪；数据：未检查");
  expect(container.textContent).toContain("小张量：未通过");
});
it("unmount closes only owned lease and late env result never publishes", async () => {
  const s = setup(),
    delayed = deferred<EnvironmentCatalog>();
  vi.mocked(s.environments.discover).mockImplementation(() => delayed.promise);
  await mount(s);
  await credentials();
  await click("认证并建立短时会话");
  await click("发现环境");
  await act(async () => root!.unmount());
  root = undefined;
  expect(s.api.close).toHaveBeenCalledWith(projectId, connectionId);
  expect(s.environments.cancel).toHaveBeenCalledWith(
    expect.objectContaining({ projectId, connectionId }),
  );
  await act(async () => delayed.resolve(s.catalog));
  expect(container.textContent).toBe("");
});
it("single-flight status polling expires session without reauthentication", async () => {
  vi.useFakeTimers();
  const s = setup(),
    delayed = deferred<AuthenticatedConnection | null>();
  vi.mocked(s.api.current).mockImplementation(() => delayed.promise);
  await mount(s);
  await credentials();
  await click("认证并建立短时会话");
  await act(async () => vi.advanceTimersByTime(5000));
  expect(s.api.current).toHaveBeenCalledTimes(1);
  await act(async () => vi.advanceTimersByTime(5000));
  expect(s.api.current).toHaveBeenCalledTimes(1);
  await act(async () => delayed.resolve(null));
  expect(s.invalidated).toHaveBeenCalledTimes(1);
  expect(s.api.authenticate).toHaveBeenCalledTimes(1);
  expect(container.textContent).not.toContain("已认证，固定会话");
});
it("cancel running environment closes session and rejects late presentation", async () => {
  const s = setup(),
    delayed = deferred<EnvironmentCatalog>();
  vi.mocked(s.environments.discover).mockImplementation(() => delayed.promise);
  await mount(s);
  await credentials();
  await click("认证并建立短时会话");
  await click("发现环境");
  await click("取消环境检查并关闭会话");
  expect(s.environments.cancel).toHaveBeenCalled();
  expect(s.api.close).toHaveBeenCalledWith(projectId, connectionId);
  await act(async () => delayed.resolve(s.catalog));
  expect(container.textContent).not.toContain("发现 1 个环境");
});
it.each([undefined, 2])(
  "invalidated pending binding clears busy and ignores old result (%s)",
  async (revision) => {
    const s = setup(),
      delayed = deferred<RemoteBinding>();
    s.report.environmentReady = true;
    s.report.dataReady = true;
    const onBinding = vi.fn();
    const remote: RemoteRunControls = {
      runs: {
        bind: vi.fn(() => delayed.promise),
      } as unknown as DesktopAPI["runs"],
      authority: { expectedRevision: 1, expectedProgramHash: "a".repeat(64) },
      onBinding,
      onSession: vi.fn(),
    };
    await mount(s, remote);
    await credentials();
    await click("认证并建立短时会话");
    await click("发现环境");
    await click("只读检查所选环境");
    await input("远端应用运行目录", "/synthetic-owned");
    await click("用于本次远端运行");
    expect(container.textContent).toContain("正在绑定…");
    await mount(s, {
      ...remote,
      authority:
        revision === undefined
          ? undefined
          : { ...remote.authority!, expectedRevision: revision },
    });
    expect(container.textContent).not.toContain("正在绑定…");
    onBinding.mockClear();
    await act(async () =>
      delayed.resolve({ bindingId: envId } as RemoteBinding),
    );
    expect(onBinding).not.toHaveBeenCalledWith(
      expect.objectContaining({ bindingId: envId }),
    );
    expect(container.querySelector("fieldset")!.disabled).toBe(false);
  },
);
