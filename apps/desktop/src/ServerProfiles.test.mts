import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { act, createElement } from "react";
import type { Root } from "react-dom/client";
import { createRequire } from "node:module";
import { mkdtemp, rm, readFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { fileURLToPath } from "node:url";
import { ServerProfiles } from "./ServerProfiles.js";
import type { ConnectionProfile, DesktopAPI } from "../electron/bridge.js";
import { MainWorkflow } from "../electron/workflow.mjs";
import { startBackend } from "../electron/backend.mjs";
const require = createRequire(import.meta.url);
const { JSDOM } = require(
  require.resolve("jsdom", { paths: [require.resolve("blockly/core")] }),
);
const projectId = "11111111-1111-4111-8111-111111111111";
const profile: ConnectionProfile = {
  alias: "课堂",
  endpoint: { host: "synthetic.invalid", port: 22 },
  username: "student",
  targetId: "22222222-2222-4222-8222-222222222222",
  revision: 1,
};
let dom: InstanceType<typeof JSDOM>, root: Root, container: HTMLDivElement;
function setup() {
  const unexpected = async (): Promise<never> => {
    throw new Error("unexpected operation");
  };
  return {
    listProfiles: vi.fn(async () => [profile]),
    createProfile: vi.fn<DesktopAPI["connections"]["createProfile"]>(
      async (input) => ({ ...input, targetId: profile.targetId, revision: 1 }),
    ),
    updateProfile: vi.fn<DesktopAPI["connections"]["updateProfile"]>(
      async (targetId, input) => ({
        alias: input.alias,
        endpoint: input.endpoint,
        username: input.username,
        targetId,
        revision: input.expectedRevision + 1,
      }),
    ),
    probe: vi.fn(unexpected),
    confirm: vi.fn(unexpected),
    authenticate: vi.fn(unexpected),
    current: vi.fn(async () => null),
    cancel: vi.fn(async () => {}),
    cancelAuth: vi.fn(async () => {}),
    close: vi.fn(async () => {}),
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
async function mount(api: DesktopAPI["connections"], id = projectId) {
  await act(async () =>
    root.render(
      createElement(ServerProfiles, {
        key: id,
        api,
        projectId: id,
        onClose: () => {},
      }),
    ),
  );
}
async function click(text: string) {
  await act(async () => {
    const button = [...container.querySelectorAll("button")].find(
      (node) => node.textContent === text,
    );
    if (!button) throw new Error(text);
    button.click();
  });
}
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
function pending<T>() {
  let resolve!: (value: T) => void, reject!: (error: unknown) => void;
  const promise = new Promise<T>((a, b) => {
    resolve = a;
    reject = b;
  });
  return { promise, resolve, reject };
}
it("lists and selects without probe/authentication, and fills locked saved endpoint", async () => {
  const api = setup();
  await mount(api);
  await click("使用此服务器：课堂");
  expect(container.textContent).toContain("已选服务器：课堂");
  const host = [...container.querySelectorAll("label")]
    .find((node) => node.textContent?.startsWith("主机名或 IP"))!
    .querySelector("input")!;
  expect(host.value).toBe(profile.endpoint.host);
  expect(host.disabled).toBe(true);
  expect(api.probe).not.toHaveBeenCalled();
  expect(api.authenticate).not.toHaveBeenCalled();
  expect(api.createProfile).not.toHaveBeenCalled();
  expect(api.updateProfile).not.toHaveBeenCalled();
});
it("saves only public fields and preserves edit input on revision conflict", async () => {
  const api = setup();
  api.listProfiles.mockResolvedValue([]);
  await mount(api);
  await enter("概要名称", "课堂");
  await enter("服务器地址", "synthetic.invalid");
  await enter("服务器账号", "student");
  await click("保存服务器概要");
  expect(api.createProfile).toHaveBeenCalledExactlyOnceWith({
    alias: "课堂",
    endpoint: profile.endpoint,
    username: "student",
  });
  expect(api.probe).not.toHaveBeenCalled();
  await click("编辑概要：课堂");
  await enter("概要名称", "new alias");
  api.updateProfile.mockRejectedValue(
    new Error("CONNECTION_PROFILE_REVISION_CONFLICT"),
  );
  await click("保存概要修改");
  expect(api.updateProfile).toHaveBeenCalledWith(profile.targetId, {
    alias: "new alias",
    endpoint: profile.endpoint,
    username: "student",
    expectedRevision: 1,
  });
  expect(container.textContent).toContain("输入已保留");
  expect(container.querySelector<HTMLInputElement>("form input")!.value).toBe(
    "new alias",
  );
  expect(container.querySelector('input[type="password"]')).toBeNull();
});
it.each(["list-success", "list-error", "save-success", "save-error"])(
  "project switch retires late %s",
  async (kind) => {
    const api = setup(),
      task = pending<ConnectionProfile[]>(),
      save = pending<ConnectionProfile>();
    if (kind.startsWith("list"))
      api.listProfiles.mockReturnValueOnce(task.promise);
    else api.createProfile.mockReturnValueOnce(save.promise);
    await mount(api);
    if (kind.startsWith("save")) {
      await enter("概要名称", "old");
      await enter("服务器地址", "old.invalid");
      await enter("服务器账号", "old");
      await click("保存服务器概要");
    }
    api.listProfiles.mockResolvedValue([]);
    await mount(api, "33333333-3333-4333-8333-333333333333");
    await act(async () => {
      if (kind === "list-success")
        task.resolve([{ ...profile, alias: "late-old" }]);
      if (kind === "list-error") task.reject(new Error("old-error"));
      if (kind === "save-success")
        save.resolve({ ...profile, alias: "late-old" });
      if (kind === "save-error") save.reject(new Error("old-error"));
    });
    expect(container.textContent).not.toContain("late-old");
    expect(container.textContent).not.toContain("old-error");
    expect(container.querySelector("[role=alert]")).toBeNull();
    expect(api.probe).not.toHaveBeenCalled();
  },
);
it("React → Main → authenticated sidecar persists and reloads profiles with stable identity and no runs", async () => {
  const directory = await mkdtemp(join(tmpdir(), "easyai-profiles-"));
  const cwd = fileURLToPath(
    new URL("../../../services/backend/", import.meta.url),
  );
  const python = join(
    cwd,
    process.platform === "win32"
      ? ".venv/Scripts/python.exe"
      : ".venv/bin/python",
  );
  let backend = await startBackend(python, cwd, 10000, directory);
  let workflow = new MainWorkflow(
    () => backend,
    async () => null,
    () => {},
  );
  const api = setup();
  api.listProfiles = vi.fn(
    async () =>
      (await workflow.invoke(
        "easyai:connections:listProfiles",
        [],
      )) as ConnectionProfile[],
  );
  api.createProfile = vi.fn(
    async (input) =>
      (await workflow.invoke("easyai:connections:createProfile", [
        input,
      ])) as ConnectionProfile,
  );
  try {
    await mount(api);
    await act(async () => {
      await api.listProfiles.mock.results[0].value;
    });
    await enter("概要名称", "课堂");
    await enter("服务器地址", "SYNTHETIC.invalid.");
    await enter("服务器账号", "student");
    await click("保存服务器概要");
    expect(api.createProfile).toHaveBeenCalledTimes(1);
    await act(async () => {
      await api.createProfile.mock.results[0].value;
    });
    const first = (await api.listProfiles())[0];
    expect(first.endpoint.host).toBe("synthetic.invalid");
    await click("使用此服务器：课堂");
    expect(api.probe).not.toHaveBeenCalled();
    expect(api.authenticate).not.toHaveBeenCalled();
    workflow.dispose();
    await backend.stop();
    backend = await startBackend(python, cwd, 10000, directory);
    workflow = new MainWorkflow(
      () => backend,
      async () => null,
      () => {},
    );
    expect(await api.listProfiles()).toEqual([first]);
    const raw = await readFile(join(directory, "connections.json"), "utf8");
    expect(raw).not.toContain("password");
    expect(raw).not.toContain("privateKey");
  } finally {
    workflow.dispose();
    await backend.stop();
    await rm(directory, { recursive: true, force: true });
  }
}, 20000);
