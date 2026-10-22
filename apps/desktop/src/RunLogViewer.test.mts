import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { act, createElement, Fragment, useState } from "react";
import type { Root } from "react-dom/client";
import { createRequire } from "node:module";
import type { DesktopAPI, RunLogs } from "../electron/bridge.js";
import { RunLogViewer } from "./RunLogViewer.js";
import {
  LOG_BOOKMARKS,
  LOG_PAGE_BYTES,
  appendRunLogs,
  emptyLogPair,
  logRows,
} from "./logWindow.js";

const require = createRequire(import.meta.url);
const { JSDOM } = require(
  require.resolve("jsdom", { paths: [require.resolve("blockly/core")] }),
);
let dom: InstanceType<typeof JSDOM>;
let root: Root | undefined;
let container: HTMLDivElement;
beforeEach(() => {
  dom = new JSDOM("<!doctype html><body></body>");
  for (const [key, value] of Object.entries({
    window: dom.window,
    document: dom.window.document,
    navigator: dom.window.navigator,
    HTMLElement: dom.window.HTMLElement,
    IS_REACT_ACT_ENVIRONMENT: true,
  }))
    vi.stubGlobal(key, value);
  // Controlled layout metrics, not a claim of real browser pixel acceptance.
  // Account for a horizontal scrollbar/border reducing the 320px viewport.
  Object.defineProperty(dom.window.HTMLElement.prototype, "clientHeight", {
    configurable: true,
    get() {
      return this.classList.contains("run-log-viewport") ? 303 : 0;
    },
  });
  Object.defineProperty(dom.window.HTMLElement.prototype, "scrollHeight", {
    configurable: true,
    get() {
      return this.classList.contains("run-log-viewport")
        ? Number.parseFloat(this.firstElementChild?.style.height ?? "0")
        : 0;
    },
  });
  container = document.createElement("div");
  document.body.append(container);
});
afterEach(async () => {
  if (root) await act(async () => root!.unmount());
  root = undefined;
  vi.unstubAllGlobals();
  dom.window.close();
});
async function render(element: ReturnType<typeof createElement>) {
  const { createRoot } = await import("react-dom/client");
  root ??= createRoot(container);
  await act(async () => root!.render(element));
}
function button(label: string) {
  const buttons = container.querySelectorAll<HTMLButtonElement>("button");
  const found = [...buttons].find((item) => item.textContent?.trim() === label);
  if (!found) throw new Error("Missing button: " + label);
  return found;
}
async function click(label: string) {
  await act(async () => button(label).click());
}
function viewport(stream = "stdout") {
  return container.querySelector<HTMLDivElement>(
    `[aria-label="${stream} 虚拟文本窗口"]`,
  )!;
}
function summary() {
  return container.querySelector('[aria-label="stdout 日志查看器"] p')!
    .textContent;
}
function fixture(stdout = "", stderr = "") {
  // ASCII text-only protocol fixture. UTF-8 byte-boundary cases use explicit
  // replies below and the existing production read_log backend regressions.
  const data = { stdout, stderr, sealed: false };
  function reply(out: number, err: number): RunLogs {
    if (out > data.stdout.length || err > data.stderr.length)
      throw new Error("fixture cursor beyond EOF");
    const a = data.stdout.slice(out, out + LOG_PAGE_BYTES);
    const b = data.stderr.slice(err, err + LOG_PAGE_BYTES);
    return {
      stdout: a,
      stdoutAfter: out + a.length,
      stderr: b,
      stderrAfter: err + b.length,
      done:
        data.sealed &&
        out + a.length === data.stdout.length &&
        err + b.length === data.stderr.length,
    };
  }
  const logs = vi.fn<DesktopAPI["runs"]["logs"]>(async (_run, out, err) =>
    reply(out, err),
  );
  const api = { runs: { logs } } as unknown as DesktopAPI;
  return { api, logs, reply, data };
}
function deferred<T>() {
  let resolve!: (value: T) => void;
  const promise = new Promise<T>((done) => (resolve = done));
  return { promise, resolve };
}

it("pins stdout while both live streams advance, then recovers old pages independently", async () => {
  const h = fixture("OLD\n".repeat(LOG_PAGE_BYTES / 4), "err0\n");
  const initial = appendRunLogs(emptyLogPair(), h.reply(0, 0));
  let push!: () => void;
  function Screen() {
    const [pair, setPair] = useState(initial);
    push = () =>
      setPair((previous) =>
        appendRunLogs(
          previous,
          h.reply(previous.stdout.end, previous.stderr.end),
        ),
      );
    return createElement(
      Fragment,
      null,
      createElement(RunLogViewer, {
        api: h.api,
        runId: "run",
        stream: "stdout",
        live: pair.stdout,
        otherEnd: pair.stderr.end,
      }),
      createElement(RunLogViewer, {
        api: h.api,
        runId: "run",
        stream: "stderr",
        live: pair.stderr,
        otherEnd: pair.stdout.end,
      }),
    );
  }
  await render(createElement(Screen));
  expect(viewport().scrollTop).toBe(viewport().scrollHeight - 303);
  await click("暂停自动滚动 stdout");
  const pinned = viewport().textContent;
  for (let n = 0; n < 5; n++) {
    h.data.stdout += "NEW\n".repeat(LOG_PAGE_BYTES / 4);
    if (!n) h.data.stderr += "ERRNEW\n";
    await act(async () => push());
  }
  expect(viewport().textContent).toBe(pinned);
  expect(viewport("stderr").textContent).toContain("ERRNEW");
  expect(container.textContent).toContain("字节已被实时读取");
  await click("恢复实时 stdout");
  expect(viewport().textContent).toContain("NEW");
  expect(viewport().textContent).not.toContain("OLD");
  expect(container.textContent).toContain("此视图不含更早的字节");
  await click("从头查看 stdout");
  expect(h.logs).toHaveBeenLastCalledWith("run", 0, h.data.stderr.length);
  expect(viewport().textContent).toContain("OLD");
  const oldPage = summary();
  await click("下一页 stdout");
  expect(h.logs).toHaveBeenLastCalledWith(
    "run",
    LOG_PAGE_BYTES,
    h.data.stderr.length,
  );
  expect(viewport().textContent).toContain("NEW");
  await click("上一页 stdout");
  expect(summary()).toBe(oldPage);
  expect(viewport("stderr").textContent).toContain("ERRNEW");
  expect(
    viewport().querySelectorAll('[role="listitem"]').length,
  ).toBeLessThanOrEqual(24);
});

it("preserves opaque UTF-8 cursors across no-progress, growth and confirmed EOF", async () => {
  const h = fixture();
  let grown = false;
  h.logs.mockImplementation(async (_run, out, err) => {
    if (out === 0)
      return {
        stdout: "A",
        stdoutAfter: 1,
        stderr: "",
        stderrAfter: err,
        done: false,
      };
    if (!grown)
      return {
        stdout: "",
        stdoutAfter: 1,
        stderr: "",
        stderrAfter: err,
        done: false,
      };
    return {
      stdout: out === 1 ? "中�" : "",
      stdoutAfter: 5, // three bytes + one invalid byte, not re-encoded length
      stderr: "",
      stderrAfter: err,
      done: true,
    };
  });
  await render(
    createElement(RunLogViewer, {
      api: h.api,
      runId: "utf8",
      stream: "stdout",
      live: emptyLogPair().stdout,
      otherEnd: 0,
    }),
  );
  await click("从头查看 stdout");
  const first = summary();
  await click("下一页 stdout");
  expect(summary()).toBe(first);
  expect(container.textContent).toContain("当前暂无新的完整文本");
  expect(button("上一页 stdout").disabled).toBe(true);
  grown = true;
  await click("下一页 stdout");
  expect(h.logs).toHaveBeenLastCalledWith("utf8", 1, 0);
  expect(viewport().textContent).toBe("中�");
  expect(container.textContent).toContain("已确认日志末尾");
  const last = summary();
  await click("下一页 stdout");
  expect(h.logs).toHaveBeenLastCalledWith("utf8", 5, 0);
  expect(summary()).toBe(last);
});

it("keeps one physical history request through resume and ignores late replies after a run switch", async () => {
  const h = fixture("old history");
  const late = deferred<RunLogs>();
  const pair = appendRunLogs(emptyLogPair(), {
    stdout: "LIVE",
    stdoutAfter: 4,
    stderr: "",
    stderrAfter: 0,
    done: false,
  });
  h.logs.mockReturnValueOnce(late.promise);
  const screen = (runId: string) =>
    createElement(RunLogViewer, {
      api: h.api,
      runId,
      stream: "stdout",
      live: pair.stdout,
      otherEnd: 0,
    });
  await render(screen("old"));
  await act(async () => {
    const head = button("从头查看 stdout");
    head.click();
    head.click();
  });
  expect(h.logs).toHaveBeenCalledTimes(1);
  await click("恢复实时 stdout");
  expect(button("从头查看 stdout").disabled).toBe(true);
  await act(async () => late.resolve(h.reply(0, 0)));
  expect(viewport().textContent).toBe("LIVE");
  expect(button("从头查看 stdout").disabled).toBe(false);
  const oldRunReply = deferred<RunLogs>();
  h.logs.mockReturnValueOnce(oldRunReply.promise);
  await click("从头查看 stdout");
  await render(screen("fresh"));
  await act(async () => oldRunReply.resolve(h.reply(0, 0)));
  expect(viewport().textContent).toBe("LIVE");
  expect(container.textContent).not.toContain("old history");
  expect(button("从头查看 stdout").disabled).toBe(false);
});

it("bounds bookmark history and virtual DOM while failures and empty pages preserve position", async () => {
  const h = fixture("x".repeat(LOG_PAGE_BYTES * (LOG_BOOKMARKS + 2)));
  await render(
    createElement(RunLogViewer, {
      api: h.api,
      runId: "many-pages",
      stream: "stdout",
      live: emptyLogPair().stdout,
      otherEnd: 0,
    }),
  );
  await click("从头查看 stdout");
  for (let n = 0; n <= LOG_BOOKMARKS; n++) {
    await click("下一页 stdout");
    expect(
      viewport().querySelectorAll('[role="listitem"]').length,
    ).toBeLessThanOrEqual(24);
  }
  expect(container.textContent).toContain("更早的页请从头读取");
  const end = summary();
  await click("下一页 stdout");
  expect(summary()).toBe(end);
  h.logs.mockRejectedValueOnce(
    new Error("private path /home/user token=secret"),
  );
  await click("上一页 stdout");
  expect(summary()).toBe(end);
  expect(container.querySelector('[role="alert"]')?.textContent).toContain(
    "读取失败",
  );
  expect(container.textContent).not.toContain("token=secret");
  for (let n = 0; n < LOG_BOOKMARKS; n++) await click("上一页 stdout");
  expect(button("上一页 stdout").disabled).toBe(true);
  expect(summary()).toContain(LOG_PAGE_BYTES.toLocaleString());
  await click("从头查看 stdout");
  expect(button("上一页 stdout").disabled).toBe(true);
  expect(container.textContent).not.toContain("更早的页请从头读取");
}, 10_000);

it("shows every long-line codepoint through a bounded virtual window and escapes HTML", async () => {
  const h = fixture();
  const raw =
    "short\n".repeat(100) +
    "<img src=x onerror=alert(1)>" +
    "😀中".repeat(1500);
  const pair = appendRunLogs(emptyLogPair(), {
    stdout: raw,
    stdoutAfter: Buffer.byteLength(raw),
    stderr: "",
    stderrAfter: 0,
    done: true,
  });
  await render(
    createElement(RunLogViewer, {
      api: h.api,
      runId: "long-text",
      stream: "stdout",
      live: pair.stdout,
      otherEnd: 0,
    }),
  );
  const expected = logRows(raw);
  expect(viewport().scrollTop).toBe(viewport().scrollHeight - 303);
  expect(
    viewport()
      .querySelector('[role="listitem"]:last-child')
      ?.getAttribute("aria-posinset"),
  ).toBe(String(expected.length));
  await click("暂停自动滚动 stdout");
  const seen = new Map<number, string>();
  for (let top = 0; top <= expected.length * 20; top += 16 * 20) {
    await act(async () => {
      viewport().scrollTop = top;
      viewport().dispatchEvent(new dom.window.Event("scroll"));
    });
    const visible = viewport().querySelectorAll('[role="listitem"]');
    expect(visible.length).toBeLessThanOrEqual(24);
    for (const row of visible)
      seen.set(
        Number(row.getAttribute("aria-posinset")),
        row.textContent ?? "",
      );
  }
  expect(
    [...seen]
      .sort(([a], [b]) => a - b)
      .map(([, text]) => text)
      .join(""),
  ).toBe(raw.replaceAll("\n", ""));
  expect(container.querySelector("img")).toBeNull();
  expect(container.querySelector("script")).toBeNull();
});
