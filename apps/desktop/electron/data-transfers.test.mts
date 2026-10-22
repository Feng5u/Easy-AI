import { it, expect, vi } from "vitest";
import { DataTransferWorkflow } from "./data-transfers.mjs";
import type { Backend } from "./backend.mjs";
import type {
  AuthenticatedConnection,
  TransferPlan,
  TransferJob,
} from "./bridge.js";

const projectId = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa";
const connectionId = "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb";
const planId = "cccccccc-cccc-4ccc-8ccc-cccccccccccc";
const request = {
  projectId,
  connectionId,
  expectedRevision: 1,
  dataSelectionId: "dddddddd-dddd-4ddd-8ddd-dddddddddddd",
  budget: { maxFiles: 2, maxBytes: 1024, seconds: 30 },
};
const plan: TransferPlan = {
  planId,
  planHash: "a".repeat(64),
  projectId,
  connectionId,
  targetId: "eeeeeeee-eeee-4eee-8eee-eeeeeeeeeeee",
  targetRevision: 1,
  sourceLabel: "/native/selected-data",
  targetPath: `/home/synthetic/.easyai/projects/${projectId}/data/${planId}`,
  fileCount: 1,
  totalBytes: 5,
  budget: request.budget,
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
  status: "UPLOADING",
  fileCount: 1,
  totalBytes: 5,
  sentBytes: 0,
  verifiedBytes: 0,
  completedFiles: 0,
  dataReady: false,
};
const confirmation = {
  projectId,
  connectionId,
  planId,
  planHash: plan.planHash,
  confirmed: true,
};
function setup() {
  let revision = 1;
  const call = vi.fn(async (_method: string, path: string) => {
    if (path === "/api/v1/local/session")
      return { project: { projectId, revision }, readOnly: false };
    if (path === "/api/v1/data-transfers/plan") return plan;
    return job;
  });
  const auth = {
    projectId,
    scope: { projectId, connectionId },
    targetId: plan.targetId,
    targetRevision: 1,
  } as AuthenticatedConnection;
  const authenticated = vi.fn(async () => auth);
  // Stable backend identity, as Main holds for the actual sidecar.
  const backend = { request: call } as unknown as Backend;
  const stable = new DataTransferWorkflow(() => backend, authenticated);
  return {
    workflow: stable,
    call,
    authenticated,
    revision: (value: number) => {
      revision = value;
    },
  };
}
it("a preview cannot upload; confirmation is exact and includes no renderer paths", async () => {
  const { workflow, call } = setup();
  expect(await workflow.invoke("easyai:dataTransfers:plan", [request])).toEqual(
    plan,
  );
  expect(
    call.mock.calls.some(([, path]) => path === "/api/v1/data-transfers"),
  ).toBe(false);
  await expect(
    workflow.invoke("easyai:dataTransfers:confirm", [
      { ...confirmation, confirmed: 1 },
    ]),
  ).rejects.toThrow();
  await expect(
    workflow.invoke("easyai:dataTransfers:plan", [
      { ...request, remotePath: "/teacher/data" },
    ]),
  ).rejects.toThrow();
  expect(
    await workflow.invoke("easyai:dataTransfers:confirm", [confirmation]),
  ).toEqual(job);
  expect(call).toHaveBeenCalledWith(
    "POST",
    "/api/v1/data-transfers",
    confirmation,
  );
  expect(
    await workflow.invoke("easyai:dataTransfers:get", [
      planId,
      { projectId, connectionId },
    ]),
  ).toEqual(job);
  expect(
    await workflow.invoke("easyai:dataTransfers:cancel", [
      planId,
      { projectId, connectionId },
    ]),
  ).toEqual(job);
});
it("retired plan, stale revision and unknown jobs cannot cause upload requests", async () => {
  const { workflow, call, revision } = setup();
  await workflow.invoke("easyai:dataTransfers:plan", [request]);
  revision(2);
  await expect(
    workflow.invoke("easyai:dataTransfers:confirm", [confirmation]),
  ).rejects.toThrow();
  revision(1);
  workflow.invalidate();
  await expect(
    workflow.invoke("easyai:dataTransfers:confirm", [confirmation]),
  ).rejects.toThrow();
  await expect(
    workflow.invoke("easyai:dataTransfers:cancel", [
      "ffffffff-ffff-4fff-8fff-ffffffffffff",
      { projectId, connectionId },
    ]),
  ).rejects.toThrow();
  expect(
    call.mock.calls.some(([, path]) => path === "/api/v1/data-transfers"),
  ).toBe(false);
});
it("rejects a completed receipt without full readback counts or with a different target", async () => {
  for (const forged of [
    { ...job, status: "COMPLETED" },
    { ...job, targetPath: "/teacher/data" },
    {
      ...job,
      errorCode: "DATA_TRANSFER_PASSWORD_SECRET",
    } as unknown as TransferJob,
  ] as TransferJob[]) {
    const { workflow, call } = setup();
    await workflow.invoke("easyai:dataTransfers:plan", [request]);
    call.mockImplementation(async (_method, path) =>
      path === "/api/v1/local/session"
        ? { project: { projectId, revision: 1 }, readOnly: false }
        : forged,
    );
    await expect(
      workflow.invoke("easyai:dataTransfers:confirm", [confirmation]),
    ).rejects.toThrow("完成核验");
  }
});

it("retains owned cancellation after a lost consuming ACK and a failed project-open attempt", async () => {
  const { workflow, call } = setup();
  await workflow.invoke("easyai:dataTransfers:plan", [request]);
  call.mockImplementation(async (_method, path) => {
    if (path === "/api/v1/local/session")
      return { project: { projectId, revision: 1 }, readOnly: false };
    if (path === "/api/v1/data-transfers")
      throw new Error("synthetic lost ACK");
    return { ...job, status: "CANCELLED" as const };
  });
  await expect(
    workflow.invoke("easyai:dataTransfers:confirm", [confirmation]),
  ).rejects.toThrow("lost ACK");
  workflow.invalidate();
  const canceled = (await workflow.invoke("easyai:dataTransfers:cancel", [
    planId,
    { projectId, connectionId },
  ])) as TransferJob;
  expect(canceled.status).toBe("CANCELLED");
  expect(call).toHaveBeenCalledWith(
    "POST",
    `/api/v1/data-transfers/${planId}/cancel`,
    { projectId, connectionId },
  );
});

it("local history cannot create a recovery grant; inspect binds the original slot and reused bytes", async () => {
  const { workflow, call } = setup();
  const slotId = "ffffffff-ffff-4fff-8fff-ffffffffffff";
  const recovered: TransferPlan = {
    ...plan,
    slotId,
    targetPath: `/home/synthetic/.easyai/projects/${projectId}/data/${slotId}`,
    reusedBytes: 5,
    missingFiles: 0,
  };
  const completed: TransferJob = {
    ...job,
    targetPath: recovered.targetPath,
    reusedBytes: 5,
    sentBytes: 0,
    verifiedBytes: 5,
    completedFiles: 1,
    status: "COMPLETED",
  };
  call.mockImplementation(async (_method, path) => {
    if (path === "/api/v1/local/session")
      return { project: { projectId, revision: 1 }, readOnly: false } as never;
    if (path.startsWith("/api/v1/data-transfers/history"))
      return [
        {
          transferId: slotId,
          projectId,
          targetId: plan.targetId,
          targetRevision: 1,
          targetPath: recovered.targetPath,
          fileCount: 1,
          totalBytes: 5,
          lastCompleted: false,
          inspectionRequired: true,
        },
      ] as never;
    if (path.endsWith("/inspect")) return recovered;
    return completed;
  });
  const history = await workflow.invoke("easyai:dataTransfers:history", [
    projectId,
  ]);
  expect(history).toHaveLength(1);
  await expect(
    workflow.invoke("easyai:dataTransfers:confirm", [confirmation]),
  ).rejects.toThrow();
  await expect(
    workflow.invoke("easyai:dataTransfers:inspect", [
      slotId,
      { ...request, path: "/arbitrary" },
    ]),
  ).rejects.toThrow();
  expect(
    await workflow.invoke("easyai:dataTransfers:inspect", [slotId, request]),
  ).toEqual(recovered);
  expect(call).toHaveBeenCalledWith(
    "POST",
    `/api/v1/data-transfers/${slotId}/inspect`,
    request,
  );
  expect(
    await workflow.invoke("easyai:dataTransfers:confirm", [confirmation]),
  ).toEqual(completed);
  workflow.invalidate();
  await expect(
    workflow.invoke("easyai:dataTransfers:confirm", [confirmation]),
  ).rejects.toThrow();
});
