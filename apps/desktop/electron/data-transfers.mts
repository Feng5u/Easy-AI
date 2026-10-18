import type { Backend } from "./backend.mjs";
import type { ProjectSession, AuthenticatedConnection } from "./bridge.js";
import type { TransferPlanRequest } from "../../../packages/contracts/types/TransferPlanRequest.js";
import type { TransferPlan } from "../../../packages/contracts/types/TransferPlan.js";
import type { TransferConfirmation } from "../../../packages/contracts/types/TransferConfirmation.js";
import type { TransferJob } from "../../../packages/contracts/types/TransferJob.js";
import type { TransferHistory } from "../../../packages/contracts/types/TransferHistory.js";
import type { SessionControl } from "../../../packages/contracts/types/SessionControl.js";

const uuid = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
const errors = new Set<NonNullable<TransferJob["errorCode"]>>([
  "DATA_TRANSFER_AUTH_STALE",
  "DATA_TRANSFER_BUSY",
  "DATA_TRANSFER_CANCELLED",
  "DATA_TRANSFER_CLEANUP_PENDING",
  "DATA_TRANSFER_CLEANUP_FAILED",
  "DATA_TRANSFER_CLOSED",
  "DATA_TRANSFER_CONFIRMATION_INVALID",
  "DATA_TRANSFER_CONFIRMATION_REQUIRED",
  "DATA_TRANSFER_FAILED",
  "DATA_TRANSFER_RECOVERY_INVALID",
  "DATA_TRANSFER_PERSISTENCE_FAILED",
  "DATA_TRANSFER_HASH_MISMATCH",
  "DATA_TRANSFER_HOME_CHANGED",
  "DATA_TRANSFER_HOME_INVALID",
  "DATA_TRANSFER_JOB_LIMIT",
  "DATA_TRANSFER_MANIFEST_LIMIT",
  "DATA_TRANSFER_NOT_FOUND",
  "DATA_TRANSFER_PLAN_EXPIRED",
  "DATA_TRANSFER_PROGRESS_INVALID",
  "DATA_TRANSFER_SOURCE_CHANGED",
  "DATA_TRANSFER_SOURCE_EMPTY",
  "DATA_TRANSFER_SOURCE_FORBIDDEN",
  "DATA_TRANSFER_SOURCE_LIMIT",
  "DATA_TRANSFER_START_FAILED",
  "DATA_TRANSFER_TARGET_REQUIRED",
  "DATA_TRANSFER_TARGET_UNOWNED",
  "DATA_TRANSFER_TIMEOUT",
  "DATA_TRANSFER_VERIFICATION_INCOMPLETE",
]);
function object(value: unknown, keys: string[]): Record<string, unknown> {
  if (
    !value ||
    typeof value !== "object" ||
    Array.isArray(value) ||
    Object.keys(value).length !== keys.length ||
    keys.some((key) => !Object.hasOwn(value, key))
  )
    throw new Error("数据上传请求字段无效。");
  return value as Record<string, unknown>;
}
function id(value: unknown): string {
  if (typeof value !== "string" || !uuid.test(value))
    throw new Error("数据上传对象无效。");
  return value;
}
function integer(value: unknown, max: number): number {
  if (!Number.isSafeInteger(value) || Number(value) < 1 || Number(value) > max)
    throw new Error("数据上传预算无效。");
  return Number(value);
}
function digest(value: unknown): string {
  if (typeof value !== "string" || !/^[0-9a-f]{64}$/.test(value))
    throw new Error("数据上传计划版本无效。");
  return value;
}

export class DataTransferWorkflow {
  private epoch = 0;
  private plans = new Map<
    string,
    { request: TransferPlanRequest; value: TransferPlan }
  >();
  private jobs = new Map<string, TransferJob>();
  private owned = new Map<
    string,
    { request: TransferPlanRequest; value: TransferPlan }
  >();
  constructor(
    private backend: () => Backend | undefined,
    private authenticated: (
      scope: SessionControl,
    ) => Promise<AuthenticatedConnection | null>,
  ) {}
  invalidate() {
    this.epoch++;
    this.plans.clear();
    // Retain owned read/cancel identities when a project-open attempt fails.
    // Actual project scope is rechecked on every request; no new upload grant.
  }
  async invoke(channel: string, args: unknown[]): Promise<unknown> {
    const backend = this.backend(),
      epoch = this.epoch;
    if (!backend) throw new Error("本地服务未就绪。");
    const verify = async (
      scope: SessionControl,
      revision?: number,
      auth = false,
    ) => {
      if (epoch !== this.epoch || backend !== this.backend())
        throw new Error("上传工程或服务已变化。");
      const current = await backend.request<ProjectSession | null>(
        "GET",
        "/api/v1/local/session",
      );
      if (
        epoch !== this.epoch ||
        backend !== this.backend() ||
        !current?.project ||
        (current.readOnly && revision !== undefined) ||
        current.project.projectId !== scope.projectId ||
        (revision !== undefined && current.project.revision !== revision)
      )
        throw new Error("上传工程或保存版本已变化。");
      const lease = auth ? await this.authenticated(scope) : null;
      if (
        auth &&
        (!lease ||
          lease.projectId !== scope.projectId ||
          lease.scope.projectId !== scope.projectId ||
          lease.scope.connectionId !== scope.connectionId)
      )
        throw new Error("上传会话已失效，请重新认证。");
      if (epoch !== this.epoch || backend !== this.backend())
        throw new Error("上传工程或服务已变化。");
      return lease;
    };
    if (channel === "easyai:dataTransfers:history") {
      if (args.length !== 1) throw new Error("数据上传参数无效。");
      const projectId = id(args[0]);
      const scope = {
        projectId,
        connectionId: "00000000-0000-0000-0000-000000000000",
      };
      await verify(scope);
      const items = await backend.request<TransferHistory[]>(
        "GET",
        `/api/v1/data-transfers/history?project_id=${projectId}`,
      );
      await verify(scope);
      if (!Array.isArray(items) || items.length > 16)
        throw new Error("上传历史无效。");
      return items.map((item) => {
        if (
          item.projectId !== projectId ||
          item.inspectionRequired !== true ||
          typeof item.lastCompleted !== "boolean" ||
          typeof item.targetPath !== "string" ||
          !item.targetPath.endsWith(
            `/.easyai/projects/${projectId}/data/${id(item.transferId)}`,
          ) ||
          item.totalBytes < 0 ||
          item.totalBytes > 256 * 1024 * 1024 ||
          !Number.isSafeInteger(item.totalBytes)
        )
          throw new Error("上传历史无效。");
        return {
          transferId: id(item.transferId),
          projectId,
          targetId: id(item.targetId),
          targetRevision: integer(item.targetRevision, Number.MAX_SAFE_INTEGER),
          targetPath: item.targetPath,
          fileCount: integer(item.fileCount, 256),
          totalBytes: item.totalBytes,
          lastCompleted: item.lastCompleted,
          inspectionRequired: true,
        };
      });
    }
    if (
      channel === "easyai:dataTransfers:plan" ||
      channel === "easyai:dataTransfers:inspect"
    ) {
      const slot = channel.endsWith(":inspect") ? id(args[0]) : null;
      if (args.length !== (slot ? 2 : 1)) throw new Error("数据上传参数无效。");
      const value = object(slot ? args[1] : args[0], [
        "projectId",
        "connectionId",
        "expectedRevision",
        "dataSelectionId",
        "budget",
      ]);
      const budget = object(value.budget, ["maxFiles", "maxBytes", "seconds"]);
      const request: TransferPlanRequest & {
        budget: Required<TransferPlanRequest["budget"]>;
      } = {
        projectId: id(value.projectId),
        connectionId: id(value.connectionId),
        expectedRevision: integer(
          value.expectedRevision,
          Number.MAX_SAFE_INTEGER,
        ),
        dataSelectionId: id(value.dataSelectionId),
        budget: {
          maxFiles: integer(budget.maxFiles, 256),
          maxBytes: integer(budget.maxBytes, 256 * 1024 * 1024),
          seconds: integer(budget.seconds, 120),
        },
      };
      const authority = await verify(request, request.expectedRevision, true);
      const plan = await backend.request<TransferPlan>(
        "POST",
        slot
          ? `/api/v1/data-transfers/${slot}/inspect`
          : "/api/v1/data-transfers/plan",
        request,
      );
      await verify(request, request.expectedRevision, true);
      if (
        !plan ||
        plan.projectId !== request.projectId ||
        plan.connectionId !== request.connectionId ||
        plan.targetId !== authority?.targetId ||
        plan.targetRevision !== authority?.targetRevision ||
        plan.budget.maxFiles !== request.budget.maxFiles ||
        plan.budget.maxBytes !== request.budget.maxBytes ||
        plan.budget.seconds !== request.budget.seconds ||
        !uuid.test(plan.planId) ||
        !/^[0-9a-f]{64}$/.test(plan.planHash) ||
        plan.writesStarted !== false ||
        (plan.slotId ?? null) !== slot ||
        !plan.targetPath.endsWith(
          `/.easyai/projects/${request.projectId}/data/${slot ?? plan.planId}`,
        ) ||
        !Number.isSafeInteger(plan.reusedBytes ?? 0) ||
        (plan.reusedBytes ?? 0) < 0 ||
        (plan.reusedBytes ?? 0) > plan.totalBytes ||
        !Number.isSafeInteger(plan.missingFiles ?? 0) ||
        (plan.missingFiles ?? 0) < 0 ||
        (plan.missingFiles ?? 0) > plan.fileCount ||
        !Number.isSafeInteger(plan.totalBytes) ||
        plan.totalBytes > request.budget.maxBytes ||
        plan.totalBytes < 0 ||
        !Number.isSafeInteger(plan.fileCount) ||
        plan.fileCount < 1 ||
        plan.fileCount > request.budget.maxFiles
      )
        throw new Error("上传计划与本次选择不一致。");
      this.plans.set(plan.planId, { request, value: plan });
      return plan;
    }
    if (channel === "easyai:dataTransfers:confirm") {
      if (args.length !== 1) throw new Error("数据上传参数无效。");
      const value = object(args[0], [
        "projectId",
        "connectionId",
        "planId",
        "planHash",
        "confirmed",
      ]);
      if (value.confirmed !== true)
        throw new Error("请明确确认数据源、远端目标与预算。");
      const request: TransferConfirmation = {
        projectId: id(value.projectId),
        connectionId: id(value.connectionId),
        planId: id(value.planId),
        planHash: digest(value.planHash),
        confirmed: true,
      };
      const plan = this.plans.get(request.planId);
      if (
        !plan ||
        plan.value.planHash !== request.planHash ||
        plan.value.projectId !== request.projectId ||
        plan.value.connectionId !== request.connectionId
      )
        throw new Error("上传计划已失效，请重新预览。");
      this.owned.set(request.planId, plan); // Own cancellation before any asynchronous confirmation gate.
      await verify(request, plan.request.expectedRevision, true);
      const job = await backend.request<TransferJob>(
        "POST",
        "/api/v1/data-transfers",
        request,
      );
      await verify(request);
      this.validate(job, request, plan.value);
      this.jobs.set(job.transferId, job);
      return job;
    }
    if (
      !["easyai:dataTransfers:get", "easyai:dataTransfers:cancel"].includes(
        channel,
      ) ||
      args.length !== 2
    )
      throw new Error("数据上传接口无效。");
    const transferId = id(args[0]),
      value = object(args[1], ["projectId", "connectionId"]);
    const scope = {
      projectId: id(value.projectId),
      connectionId: id(value.connectionId),
    };
    const known = this.owned.get(transferId)?.value;
    if (
      !known ||
      known.projectId !== scope.projectId ||
      known.connectionId !== scope.connectionId
    )
      throw new Error("数据上传任务不属于当前会话。");
    await verify(scope);
    const job = channel.endsWith(":cancel")
      ? await backend.request<TransferJob>(
          "POST",
          `/api/v1/data-transfers/${transferId}/cancel`,
          scope,
        )
      : await backend.request<TransferJob>(
          "GET",
          `/api/v1/data-transfers/${transferId}?project_id=${scope.projectId}&connection_id=${scope.connectionId}`,
        );
    await verify(scope);
    this.validate(job, scope, known);
    if (job.transferId !== transferId) throw new Error("上传任务回执不一致。");
    this.jobs.set(transferId, job);
    return job;
  }
  private validate(
    job: TransferJob,
    scope: SessionControl,
    plan: TransferPlan,
  ) {
    if (
      !job ||
      job.projectId !== scope.projectId ||
      job.connectionId !== scope.connectionId ||
      job.transferId !== plan.planId ||
      job.planId !== plan.planId ||
      job.planHash !== plan.planHash ||
      job.targetPath !== plan.targetPath ||
      job.totalBytes !== plan.totalBytes ||
      job.fileCount !== plan.fileCount ||
      job.dataReady !== false ||
      (job.errorCode != null && !errors.has(job.errorCode)) ||
      typeof job.sentBytes !== "number" ||
      typeof job.verifiedBytes !== "number" ||
      typeof job.completedFiles !== "number" ||
      ![
        "UPLOADING",
        "VERIFYING",
        "CANCELLING",
        "CLEANUP_PENDING",
        "COMPLETED",
        "CANCELLED",
        "FAILED",
      ].includes(job.status) ||
      (job.reusedBytes ?? 0) !== (plan.reusedBytes ?? 0) ||
      ![
        job.sentBytes,
        job.verifiedBytes,
        job.completedFiles,
        job.reusedBytes ?? 0,
      ].every(Number.isSafeInteger) ||
      job.sentBytes < 0 ||
      job.sentBytes > plan.totalBytes ||
      job.verifiedBytes < 0 ||
      job.verifiedBytes > plan.totalBytes ||
      job.completedFiles < 0 ||
      job.completedFiles > plan.fileCount ||
      (job.status === "COMPLETED" &&
        (job.sentBytes + (job.reusedBytes ?? 0) !== plan.totalBytes ||
          job.verifiedBytes !== plan.totalBytes ||
          job.completedFiles !== plan.fileCount))
    )
      throw new Error("上传任务结果未通过身份或完成核验。");
  }
}
