/// <reference types="node" />
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { act, createElement } from "react";
import type { Root } from "react-dom/client";
import { createRequire } from "node:module";
import { ConnectionPanel } from "./ConnectionPanel.js";
import type { DesktopAPI, IdentityResult } from "../electron/bridge.js";
const require = createRequire(import.meta.url);
const { JSDOM } = require(
  require.resolve("jsdom", { paths: [require.resolve("blockly/core")] }),
);
const project = "11111111-1111-4111-8111-111111111111";
const fp = "SHA256:" + "A".repeat(43);
let root: Root | undefined,
  dom: InstanceType<typeof JSDOM>,
  container: HTMLDivElement;
function result(
  projectId: string,
  requestId: string,
  state: "unknown" | "changed" | "trusted" = "unknown",
): IdentityResult {
  return {
    projectId,
    requestId,
    observation: {
      endpoint: { host: "offline.invalid", port: 22 },
      algorithm: "ssh-ed25519",
      fingerprint: fp,
      trustState: state,
      challengeId:
        state === "unknown" ? "22222222-2222-4222-8222-222222222222" : null,
      previousFingerprint:
        state === "changed" ? "SHA256:" + "B".repeat(43) : null,
    },
  };
}
function setup() {
  const api = {
    authenticate: vi.fn<DesktopAPI["connections"]["authenticate"]>(),
    cancelAuth: vi.fn<DesktopAPI["connections"]["cancelAuth"]>(async () => {}),
    close: vi.fn<DesktopAPI["connections"]["close"]>(async () => {}),
    current: vi.fn<DesktopAPI["connections"]["current"]>(async () => null),
    probe: vi.fn<DesktopAPI["connections"]["probe"]>(async (pid, rid) =>
      result(pid, rid),
    ),
    confirm: vi.fn<DesktopAPI["connections"]["confirm"]>(async (pid, rid) =>
      result(pid, rid, "trusted"),
    ),
    cancel: vi.fn<DesktopAPI["connections"]["cancel"]>(async () => {}),
  };
  return api;
}
function button(label: string): HTMLButtonElement {
  const value = [...container.querySelectorAll("button")].find(
    (item) => item.textContent === label,
  );
  if (!value) throw new Error("Missing button: " + label);
  return value;
}
async function click(label: string) {
  await act(async () => button(label).click());
}
async function setHost(value: string) {
  await act(async () => {
    const input = container.querySelector("input")!;
    Object.getOwnPropertyDescriptor(
      dom.window.HTMLInputElement.prototype,
      "value",
    )!.set!.call(input, value);
    input.dispatchEvent(new dom.window.Event("input", { bubbles: true }));
  });
}
async function mount(api: DesktopAPI["connections"], id = project) {
  if (!root) {
    const { createRoot } = await import("react-dom/client");
    root = createRoot(container);
  }
  await act(async () =>
    root!.render(
      createElement(ConnectionPanel, {
        api,
        projectId: id,
        key: id,
        onClose: () => {
          void act(() => root!.unmount());
          root = undefined;
        },
      }),
    ),
  );
}
function deferred<T>() {
  let resolve!: (value: T) => void, reject!: (error: Error) => void;
  const promise = new Promise<T>((a, b) => {
    resolve = a;
    reject = b;
  });
  return { promise, resolve, reject };
}
beforeEach(() => {
  dom = new JSDOM("<!doctype html><html><body></body></html>", {
    url: "https://component.test/",
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
it("unknown requires explicit verification; changed has no override; trusted never says authenticated", async () => {
  const api = setup();
  await mount(api);
  await setHost("offline.invalid");
  await click("检查主机指纹");
  expect(button("确认信任此指纹").disabled).toBe(true);
  await act(async () =>
    (
      container.querySelector('input[type="checkbox"]') as HTMLInputElement
    ).click(),
  );
  await click("确认信任此指纹");
  expect(api.confirm).toHaveBeenCalledWith(
    project,
    api.probe.mock.calls[0][1],
    fp,
  );
  expect(container.textContent).toContain("信任指纹本身不代表用户认证");
  api.probe.mockImplementation(async (pid, rid) => result(pid, rid, "changed"));
  await click("重新检查主机指纹");
  expect(container.textContent).toContain("主机密钥已变化，已拒绝信任");
  expect(
    [...container.querySelectorAll("button")].some(
      (item) => item.textContent === "确认信任此指纹",
    ),
  ).toBe(false);
  expect(api.confirm).toHaveBeenCalledTimes(1);
});
it("target edit and cancellation discard late success and late rejection", async () => {
  const api = setup(),
    first = deferred<IdentityResult>();
  api.probe.mockReturnValueOnce(first.promise);
  await mount(api);
  await setHost("offline.invalid");
  await click("检查主机指纹");
  const old = api.probe.mock.calls[0][1];
  await setHost("other.invalid");
  expect(api.cancel).toHaveBeenCalledWith(project, old);
  await act(async () => first.resolve(result(project, old)));
  expect(container.querySelector('[aria-label="主机指纹结果"]')).toBeNull();
  expect(button("检查主机指纹").disabled).toBe(false);
  const second = deferred<IdentityResult>();
  api.probe.mockReturnValueOnce(second.promise);
  await click("检查主机指纹");
  await click("取消检查");
  await act(async () => second.reject(new Error("DO_NOT_SHOW_SDK_SECRET")));
  expect(container.textContent).not.toContain("DO_NOT_SHOW");
  expect(container.textContent).toContain("旧响应已失效");
});
it("editing during confirm cannot display stale trust and project switch resets target", async () => {
  const api = setup(),
    confirmation = deferred<IdentityResult>();
  api.confirm.mockReturnValueOnce(confirmation.promise);
  await mount(api);
  await setHost("offline.invalid");
  await click("检查主机指纹");
  await act(async () =>
    (
      container.querySelector('input[type="checkbox"]') as HTMLInputElement
    ).click(),
  );
  await click("确认信任此指纹");
  const old = api.probe.mock.calls[0][1];
  await setHost("other.invalid");
  await act(async () => confirmation.resolve(result(project, old, "trusted")));
  expect(container.textContent).not.toContain("与信任记录一致");
  await click("检查主机指纹");
  await mount(api, "33333333-3333-4333-8333-333333333333");
  expect((container.querySelector("input") as HTMLInputElement).value).toBe("");
  expect(container.querySelector('[aria-label="主机指纹结果"]')).toBeNull();
  expect(api.cancel).toHaveBeenCalledWith(project, api.probe.mock.calls[1][1]);
});
it("25-second UI deadline and unmount invalidate operations without an automatic reconnect", async () => {
  vi.useFakeTimers();
  const api = setup(),
    waiting = deferred<IdentityResult>();
  api.probe.mockReturnValue(waiting.promise);
  await mount(api);
  await setHost("offline.invalid");
  await click("检查主机指纹");
  await act(async () => {
    await vi.advanceTimersByTimeAsync(25000);
  });
  expect(container.textContent).toContain("等待已超时");
  expect(api.probe).toHaveBeenCalledTimes(1);
  const old = api.probe.mock.calls[0][1];
  await act(async () => waiting.resolve(result(project, old)));
  expect(container.querySelector('[aria-label="主机指纹结果"]')).toBeNull();
  const next = deferred<IdentityResult>();
  api.probe.mockReturnValueOnce(next.promise);
  await click("检查主机指纹");
  await act(async () => root!.unmount());
  root = undefined;
  expect(api.cancel).toHaveBeenCalledWith(project, api.probe.mock.calls[1][1]);
  await act(async () =>
    next.resolve(result(project, api.probe.mock.calls[1][1])),
  );
});
it("failed probe resets busy and hides raw error input", async () => {
  const api = setup();
  api.probe.mockRejectedValueOnce(
    new Error("SSH_TRUST_PERMISSIONS_UNSAFE DO_NOT_ECHO"),
  );
  await mount(api);
  await setHost("offline.invalid");
  await click("检查主机指纹");
  expect(container.textContent).toContain("权限不安全");
  expect(container.textContent).not.toContain("DO_NOT_ECHO");
  expect(button("检查主机指纹").disabled).toBe(false);
});
