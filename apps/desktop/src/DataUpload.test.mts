import { beforeEach, afterEach, it, expect, vi } from "vitest";
import { act, createElement } from "react";
import type { Root } from "react-dom/client";
import { createRequire } from "node:module";
import { DataUpload } from "./DataUpload.js";
import type {
  DesktopAPI,
  AuthenticatedConnection,
  TransferPlan,
  TransferJob,
} from "../electron/bridge.js";
const require = createRequire(import.meta.url);
const { JSDOM } = require(
  require.resolve("jsdom", { paths: [require.resolve("blockly/core")] }),
);
let dom: InstanceType<typeof JSDOM>, root: Root, container: HTMLDivElement;
const projectId = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
  connectionId = "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb",
  planId = "cccccccc-cccc-4ccc-8ccc-cccccccccccc";
const session = {
  projectId,
  username: "synthetic",
  scope: { projectId, connectionId, hostFingerprint: "SHA256:synthetic" },
} as AuthenticatedConnection;
const plan: TransferPlan = {
  planId,
  planHash: "a".repeat(64),
  projectId,
  connectionId,
  targetId: "dddddddd-dddd-4ddd-8ddd-dddddddddddd",
  targetRevision: 1,
  sourceLabel: "/selected/synthetic-data",
  targetPath: `/home/synthetic/.easyai/projects/${projectId}/data/${planId}`,
  fileCount: 1,
  totalBytes: 5,
  budget: { maxFiles: 64, maxBytes: 256 * 1024 * 1024, seconds: 120 },
  expiresInSeconds: 60,
  writesStarted: false,
};
const job: TransferJob = {
  transferId: planId,
  planId,
  planHash: plan.planHash,
  projectId,
  connectionId,
  targetPath: plan.targetPath,
  fileCount: 1,
  totalBytes: 5,
  sentBytes: 0,
  verifiedBytes: 0,
  completedFiles: 0,
  status: "UPLOADING",
  dataReady: false,
};
beforeEach(async () => {
  dom = new JSDOM("<!doctype html><body></body>");
  vi.stubGlobal("window", dom.window);
  vi.stubGlobal("document", dom.window.document);
  vi.stubGlobal("navigator", dom.window.navigator);
  vi.stubGlobal("IS_REACT_ACT_ENVIRONMENT", true);
  container = document.createElement("div");
  document.body.append(container);
  const { createRoot } = await import("react-dom/client");
  root = createRoot(container);
  vi.useFakeTimers();
});
afterEach(async () => {
  await act(async () => root.unmount());
  vi.useRealTimers();
  vi.unstubAllGlobals();
  dom.window.close();
});
function fixture() {
  const calls = {
    plan: vi.fn(async () => plan),
    confirm: vi.fn(async () => job),
    get: vi.fn(async () => job),
    cancel: vi.fn(async (): Promise<TransferJob> => ({
      ...job,
      status: "CANCELLING",
    })),
  };
  const pick = vi.fn(async () => ({
    selectionId: "eeeeeeee-eeee-4eee-8eee-eeeeeeeeeeee",
    kind: "data" as const,
    label: plan.sourceLabel,
  }));
  const api = {
    selections: { pick },
    dataTransfers: calls,
  } as unknown as DesktopAPI;
  return { api, calls, pick };
}
async function mount(api: DesktopAPI, revision = 1) {
  await act(async () =>
    root.render(
      createElement(DataUpload, { api, session, revision, disabled: false }),
    ),
  );
}
async function click(label: string) {
  await act(async () =>
    [...container.querySelectorAll<HTMLButtonElement>("button")]
      .find((b) => b.textContent === label)!
      .click(),
  );
}
it("requires native selection, preview and explicit checkbox before upload; completion still requires data probe", async () => {
  const { api, calls, pick } = fixture();
  await mount(api);
  expect(calls.plan).not.toHaveBeenCalled();
  expect(calls.confirm).not.toHaveBeenCalled();
  await click("选择上传数据目录");
  expect(pick).toHaveBeenCalledWith("data");
  await click("预览上传计划（不写远端）");
  expect(container.textContent).toContain(plan.targetPath);
  await click("确认并上传数据");
  expect(calls.confirm).not.toHaveBeenCalled();
  await act(async () =>
    container
      .querySelector<HTMLInputElement>('input[type="checkbox"]')!
      .click(),
  );
  await click("确认并上传数据");
  expect(calls.confirm).toHaveBeenCalledExactlyOnceWith({
    projectId,
    connectionId,
    planId,
    planHash: plan.planHash,
    confirmed: true,
  });
  calls.get.mockResolvedValue({
    ...job,
    status: "COMPLETED",
    sentBytes: 5,
    verifiedBytes: 5,
    completedFiles: 1,
  });
  await act(async () => {
    await vi.advanceTimersByTimeAsync(1000);
  });
  expect(container.textContent).toContain("这不代表 Dataset 已就绪");
});
it("cancel is a request; unknown cleanup remains visible and scope changes retire late polling", async () => {
  const { api, calls } = fixture();
  await mount(api);
  await click("选择上传数据目录");
  await click("预览上传计划（不写远端）");
  await act(async () =>
    container
      .querySelector<HTMLInputElement>('input[type="checkbox"]')!
      .click(),
  );
  await click("确认并上传数据");
  await click("请求停止上传");
  expect(container.textContent).toContain("CANCELLING");
  calls.get.mockResolvedValue({ ...job, status: "CLEANUP_PENDING" });
  await act(async () => {
    await vi.advanceTimersByTimeAsync(1000);
  });
  expect(container.textContent).toContain("CLEANUP_PENDING");
  await mount(api, 2);
  const count = calls.get.mock.calls.length;
  await act(async () => {
    await vi.advanceTimersByTimeAsync(2000);
  });
  expect(calls.get).toHaveBeenCalledTimes(count);
  expect(container.textContent).not.toContain("上传状态：COMPLETED");
});

it("can cancel an unacknowledged start and ignores its late completion reply", async () => {
  const { api, calls } = fixture();
  let finish!: (value: TransferJob) => void;
  calls.confirm.mockImplementation(
    () =>
      new Promise<TransferJob>((resolve) => {
        finish = resolve;
      }),
  );
  calls.cancel.mockResolvedValue({ ...job, status: "CANCELLED" });
  await mount(api);
  await click("选择上传数据目录");
  await click("预览上传计划（不写远端）");
  await act(async () =>
    container
      .querySelector<HTMLInputElement>('input[type="checkbox"]')!
      .click(),
  );
  await click("确认并上传数据");
  expect(container.textContent).toContain("上传开始尚未确认");
  await click("请求停止未确认上传");
  expect(calls.cancel).toHaveBeenCalledWith(planId, {
    projectId,
    connectionId,
  });
  expect(container.textContent).toContain("上传状态：CANCELLED");
  await act(async () => {
    finish({
      ...job,
      status: "COMPLETED",
      sentBytes: 5,
      verifiedBytes: 5,
      completedFiles: 1,
    });
  });
  expect(container.textContent).not.toContain("上传状态：COMPLETED");
});
