import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { act, createElement } from "react";
import type { Root } from "react-dom/client";
import { createRequire } from "node:module";
import { GettingStarted } from "./GettingStarted.js";
import type { GettingStartedProps } from "./GettingStarted.js";
const require = createRequire(import.meta.url);
const { JSDOM } = require(
  require.resolve("jsdom", { paths: [require.resolve("blockly/core")] }),
);
let dom: InstanceType<typeof JSDOM>, root: Root, container: HTMLDivElement;
beforeEach(async () => {
  dom = new JSDOM("<!doctype html><html><body></body></html>", {
    url: "http://localhost",
  });
  vi.stubGlobal("window", dom.window);
  vi.stubGlobal("document", dom.window.document);
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
function props(): GettingStartedProps {
  return {
    projectName: null,
    readOnly: false,
    dirty: false,
    mode: "local",
    pythonSelected: false,
    dataSelected: false,
    remoteBound: false,
    compiled: false,
    hasRun: false,
    ready: true,
    blocked: false,
    onNavigate: vi.fn(),
    onServer: vi.fn(),
  };
}
async function render(value: GettingStartedProps) {
  await act(async () => root.render(createElement(GettingStarted, value)));
}
async function click(text: string) {
  await act(async () => {
    [...container.querySelectorAll("button")]
      .find((node) => node.textContent === text)!
      .click();
  });
}
it("welcomes without executing actions and offers only explicit navigation", async () => {
  const value = props();
  await render(value);
  expect(container.textContent).toContain("尚未打开工程");
  expect(container.textContent).toContain("不会启动训练");
  expect(value.onNavigate).not.toHaveBeenCalled();
  expect(value.onServer).not.toHaveBeenCalled();
  await click("前往工程设置");
  expect(value.onNavigate).toHaveBeenCalledExactlyOnceWith("project");
});
it("selected Python/data is never presented as passed preflight or training", async () => {
  const value = {
    ...props(),
    projectName: "课堂",
    pythonSelected: true,
    dataSelected: true,
    compiled: true,
  };
  await render(value);
  expect(container.textContent).toContain("选择完成不代表预检通过");
  expect(container.textContent).toContain("环境与数据仍需分别检查");
  await render({ ...value, dirty: true });
  expect(container.textContent).toContain("先保存当前修改");
  expect(container.textContent).not.toContain("当前保存版本的代码检查通过");
});
it("server guide needs no local copies and blocked state cannot open configuration", async () => {
  const value = {
    ...props(),
    projectName: "课堂",
    mode: "ssh" as const,
    blocked: true,
  };
  await render(value);
  expect(container.textContent).toContain("不要求本机有数据副本");
  await click("配置服务器环境与数据");
  expect(value.onServer).not.toHaveBeenCalled();
  await render({ ...value, blocked: false });
  await click("配置服务器环境与数据");
  expect(value.onServer).toHaveBeenCalledTimes(1);
  await render({ ...value, remoteBound: true });
  expect(container.textContent).toContain("开始运行时仍会复检");
});
it("readonly and not-ready states do not claim runnable setup", async () => {
  await render({ ...props(), readOnly: true, ready: false });
  expect(container.textContent).toContain("不能修改或启动训练");
  expect(container.textContent).toContain("本地服务尚未就绪");
  expect(container.textContent).not.toContain("当前保存版本的代码检查通过");
});
