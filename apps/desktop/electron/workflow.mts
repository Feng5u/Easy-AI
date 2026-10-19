import { safeReport } from "./diagnostic-report.mjs";
import { publishNewReport } from "./atomic-report.mjs";
import { isAbsolute } from "node:path";
import { SessionWorkflow } from "./session-workflow.mjs";
import { DataTransferWorkflow } from "./data-transfers.mjs";
import { IdentityWorkflow, endpoint } from "./identity-workflow.mjs";
import type { Backend } from "./backend.mjs";
import type {
  ProjectDocument,
  ProjectSession,
  BundleExportResult,
  AuthenticatedConnection,
  SelectionKind,
  StartRun,
  SubscriptionMessage,
} from "./bridge.js";

const uuid = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
export const WORKFLOW_CHANNELS = [
  "easyai:dataTransfers:plan",
  "easyai:dataTransfers:history",
  "easyai:dataTransfers:inspect",
  "easyai:dataTransfers:confirm",
  "easyai:dataTransfers:get",
  "easyai:dataTransfers:cancel",
  "easyai:packages:catalog",
  "easyai:packages:plan",
  "easyai:packages:chooseSources",
  "easyai:packages:confirmSources",
  "easyai:installJobs:confirm",
  "easyai:installJobs:get",
  "easyai:installJobs:list",
  "easyai:installJobs:report",
  "easyai:installJobs:cancel",
  "easyai:installJobs:reconcile",
  "easyai:connections:listProfiles",
  "easyai:connections:createProfile",
  "easyai:connections:updateProfile",
  "easyai:local:preflight",
  "easyai:connections:authenticate",
  "easyai:connections:authenticateKey",
  "easyai:connections:cancelAuth",
  "easyai:connections:close",
  "easyai:connections:current",
  "easyai:environments:discover",
  "easyai:environments:probe",
  "easyai:environments:cancel",

  "easyai:connections:probe",
  "easyai:connections:confirm",
  "easyai:connections:cancel",
  "easyai:selections:pick",
  "easyai:projects:current",
  "easyai:projects:open",
  "easyai:projects:create",
  "easyai:projects:import",
  "easyai:projects:export",
  "easyai:projects:exportBundle",
  "easyai:projects:save",
  "easyai:projects:compile",
  "easyai:runs:start",
  "easyai:runs:bind",
  "easyai:runs:resume",
  "easyai:runs:list",
  "easyai:runs:get",
  "easyai:runs:cancel",
  "easyai:runs:source",
  "easyai:runs:report",
  "easyai:runs:exportDiagnostic",
  "easyai:runs:logs",
  "easyai:runs:artifacts",
  "easyai:runs:pauseArtifactSync",
  "easyai:runs:resumeArtifactSync",
  "easyai:runs:image",
] as const;
function id(value: unknown): string {
  if (typeof value !== "string" || !uuid.test(value))
    throw new Error("对象标识无效。");
  return value;
}
function integer(value: unknown, minimum = 0): number {
  if (!Number.isSafeInteger(value) || Number(value) < minimum)
    throw new Error("版本或游标无效。");
  return Number(value);
}
function object(value: unknown, keys?: string[]): Record<string, unknown> {
  if (!value || typeof value !== "object" || Array.isArray(value))
    throw new Error("请求格式无效。");
  const record = value as Record<string, unknown>;
  if (
    keys &&
    (Object.keys(record).length !== keys.length ||
      keys.some((key) => !Object.hasOwn(record, key)))
  )
    throw new Error("请求字段无效。");
  return record;
}
function project(value: unknown): ProjectDocument {
  const record = object(value);
  id(record.projectId);
  integer(record.revision, 1);
  if (Buffer.byteLength(JSON.stringify(value), "utf8") > 5 * 1024 * 1024)
    throw new Error("工程超过大小限制。");
  return value as ProjectDocument;
}
export class MainWorkflow {
  private sourceEpoch = 0;
  private sourceReceipt?: { id: string; hash: string; backend: Backend };
  private reportEpoch = 0;
  private sessions: SessionWorkflow;
  private transfers: DataTransferWorkflow;
  private identity: IdentityWorkflow;
  private subscriptions = new Map<string, AbortController>();
  constructor(
    private backend: () => Backend | undefined,
    private choose: (kind: SelectionKind) => Promise<string | null>,
    private send: (message: SubscriptionMessage) => void,
    private files?: {
      importProject(): Promise<{
        sourcePath: string;
        destinationPath: string;
      } | null>;
      exportProject(): Promise<string | null>;
      exportBundle?(): Promise<string | null>;
      exportDiagnostic?(): Promise<string | null>;
      privateKey?(): Promise<string | null>;
      installSources?(): Promise<string | null>;
    },
  ) {
    this.identity = new IdentityWorkflow(backend);
    this.sessions = new SessionWorkflow(
      backend,
      this.identity,
      files?.privateKey,
    );
    this.transfers = new DataTransferWorkflow(
      backend,
      async (scope) =>
        (await this.sessions.invoke("easyai:connections:current", [
          scope.projectId,
          scope.connectionId,
        ])) as AuthenticatedConnection | null,
    );
  }
  async invoke(channel: string, args: unknown[]): Promise<unknown> {
    if (channel.startsWith("easyai:dataTransfers:"))
      return this.transfers.invoke(channel, args);
    if (
      [
        "easyai:connections:authenticate",
        "easyai:connections:authenticateKey",
        "easyai:connections:cancelAuth",
        "easyai:connections:close",
        "easyai:connections:current",
        "easyai:environments:discover",
        "easyai:environments:probe",
        "easyai:environments:cancel",
      ].includes(channel)
    )
      return this.sessions.invoke(channel, args);
    if (channel === "easyai:connections:probe") this.sessions.invalidate();
    if (channel === "easyai:connections:cancel")
      this.sessions.cancelIdentity(args[0], args[1]);
    if (
      channel === "easyai:connections:probe" ||
      channel === "easyai:connections:confirm" ||
      channel === "easyai:connections:cancel"
    )
      return this.identity.invoke(channel, args);
    const backend = this.backend();
    if (!backend) throw new Error("本地服务未就绪。");
    const counts: Record<string, number> = {
      "easyai:packages:catalog": 0,
      "easyai:packages:plan": 1,
      "easyai:packages:chooseSources": 1,
      "easyai:packages:confirmSources": 1,
      "easyai:installJobs:confirm": 1,
      "easyai:installJobs:get": 1,
      "easyai:installJobs:list": 0,
      "easyai:installJobs:report": 1,
      "easyai:installJobs:cancel": 1,
      "easyai:installJobs:reconcile": 3,
      "easyai:connections:listProfiles": 0,
      "easyai:connections:createProfile": 1,
      "easyai:connections:updateProfile": 2,
      "easyai:local:preflight": 1,
      "easyai:selections:pick": 1,
      "easyai:projects:current": 0,
      "easyai:projects:open": 1,
      "easyai:projects:create": 2,
      "easyai:projects:import": 0,
      "easyai:projects:export": 0,
      "easyai:projects:exportBundle": 3,
      "easyai:projects:save": 2,
      "easyai:projects:compile": 2,
      "easyai:runs:start": 1,
      "easyai:runs:bind": 1,
      "easyai:runs:resume": 3,
      "easyai:runs:list": 3,
      "easyai:runs:get": 1,
      "easyai:runs:cancel": 1,
      "easyai:runs:source": 1,
      "easyai:runs:report": 2,
      "easyai:runs:exportDiagnostic": 2,
      "easyai:runs:logs": 3,
      "easyai:runs:artifacts": 1,
      "easyai:runs:pauseArtifactSync": 1,
      "easyai:runs:resumeArtifactSync": 1,
      "easyai:runs:image": 2,
    };
    if (
      !Object.hasOwn(counts, channel) ||
      (args.length !== counts[channel] &&
        !(channel === "easyai:projects:create" && args.length === 3) &&
        !(channel === "easyai:projects:export" && args.length === 1))
    )
      throw new Error("IPC接口或参数无效。");
    if (
      [
        "easyai:projects:open",
        "easyai:projects:create",
        "easyai:projects:import",
      ].includes(channel)
    ) {
      this.reportEpoch += 1;
      this.transfers.invalidate();
      this.sessions.invalidate();
      this.identity.invalidate();
    }
    switch (channel) {
      case "easyai:packages:chooseSources": {
        const value = object(args[0], ["packageIds"]);
        if (
          !Array.isArray(value.packageIds) ||
          value.packageIds.length < 1 ||
          value.packageIds.length > 17 ||
          new Set(value.packageIds).size !== value.packageIds.length ||
          value.packageIds.some(
            (item) =>
              typeof item !== "string" || !/^[a-z][a-z0-9-]{0,63}$/.test(item),
          )
        )
          throw Error("来源预览包选择无效。");
        const epoch = ++this.sourceEpoch;
        this.sourceReceipt = undefined;
        if (!this.files?.installSources) throw Error("本地来源选择器不可用。");
        const selected = await this.files.installSources();
        if (epoch !== this.sourceEpoch || backend !== this.backend())
          throw Error("来源会话已变化。");
        if (!selected) return null;
        const result = await backend.request(
          "POST",
          "/api/v1/environments/install-source/preview",
          {
            manifestPath: selected,
            packageIds: [...value.packageIds],
          },
        );
        if (epoch !== this.sourceEpoch || backend !== this.backend())
          throw Error("来源会话已变化。");
        const preview = object(result);
        if (
          typeof preview.previewHash !== "string" ||
          !/^[a-f0-9]{64}$/.test(preview.previewHash)
        )
          throw Error("来源预览标识无效。");
        this.sourceReceipt = {
          id: id(preview.previewId),
          hash: preview.previewHash,
          backend,
        };
        return result;
      }
      case "easyai:packages:confirmSources": {
        const value = object(args[0], [
          "previewId",
          "previewHash",
          "confirmed",
        ]);
        const receipt = this.sourceReceipt;
        if (
          !receipt ||
          receipt.backend !== backend ||
          value.confirmed !== true ||
          id(value.previewId) !== receipt.id ||
          value.previewHash !== receipt.hash
        )
          throw Error("请重新选择并明确核对来源预览。");
        const epoch = this.sourceEpoch;
        const result = await backend.request(
          "POST",
          "/api/v1/environments/install-source/confirm",
          {
            previewId: receipt.id,
            previewHash: receipt.hash,
            confirmed: true,
          },
        );
        if (
          epoch !== this.sourceEpoch ||
          this.backend() !== backend ||
          this.sourceReceipt !== receipt
        )
          throw Error("来源会话已变化，登记结果需重新核对。");
        return result;
      }
      case "easyai:connections:listProfiles":
        return backend.request("GET", "/api/v1/connections");
      case "easyai:connections:createProfile":
      case "easyai:connections:updateProfile": {
        const update = channel === "easyai:connections:updateProfile";
        const value = object(
          args[update ? 1 : 0],
          update
            ? ["alias", "endpoint", "username", "expectedRevision"]
            : ["alias", "endpoint", "username"],
        );
        if (
          typeof value.alias !== "string" ||
          !value.alias ||
          value.alias.length > 80 ||
          /[\x00-\x1f\x7f]/.test(value.alias) ||
          typeof value.username !== "string" ||
          !value.username ||
          value.username.length > 128 ||
          /[\x00-\x20\x7f]/.test(value.username)
        )
          throw new Error("CONNECTION_PROFILE_INVALID");
        const input = {
          alias: value.alias,
          endpoint: endpoint(value.endpoint),
          username: value.username,
        };
        if (!update)
          return backend.request("POST", "/api/v1/connections", input);
        const targetId = id(args[0]);
        const expectedRevision = integer(value.expectedRevision, 1);
        this.sessions.invalidateTarget(targetId);
        return backend.request("PATCH", `/api/v1/connections/${targetId}`, {
          ...input,
          expectedRevision,
        });
      }

      case "easyai:local:preflight": {
        const value = object(args[0], [
          "projectId",
          "expectedRevision",
          "pythonSelectionId",
          "dataSelectionId",
        ]);
        const request = {
          projectId: id(value.projectId),
          expectedRevision: integer(value.expectedRevision, 1),
          pythonSelectionId: id(value.pythonSelectionId),
          dataSelectionId: id(value.dataSelectionId),
        };
        return backend.request("POST", "/api/v1/local/preflight", request);
      }

      case "easyai:selections:pick": {
        const kind = args[0];
        if (
          typeof kind !== "string" ||
          !["project", "python", "data"].includes(kind)
        )
          throw new Error("选择类型无效。");
        const path = await this.choose(kind as SelectionKind);
        return path === null
          ? null
          : backend.request("POST", "/api/v1/local/selections", { kind, path });
      }
      case "easyai:projects:current":
        return backend.request("GET", "/api/v1/local/session");
      case "easyai:projects:open":
        return backend.request("POST", "/api/v1/projects/open", {
          selectionId: id(args[0]),
        });
      case "easyai:projects:create": {
        if (
          typeof args[1] !== "string" ||
          !args[1].trim() ||
          args[1].length > 128
        )
          throw new Error("项目名称无效。");
        const template = args[2] ?? "mnist-cnn";
        if (template !== "mnist-cnn" && template !== "blank")
          throw new Error("工程模板无效。");
        return backend.request("POST", "/api/v1/projects", {
          selectionId: id(args[0]),
          name: args[1],
          template,
        });
      }
      case "easyai:projects:import": {
        if (!this.files) throw new Error("原生文件选择不可用。");
        const selection = await this.files.importProject();
        return selection
          ? backend.request("POST", "/api/v1/local/import", selection)
          : null;
      }
      case "easyai:projects:export": {
        if (!this.files) throw new Error("原生文件选择不可用。");
        const document = args.length ? project(args[0]) : undefined;
        const path = await this.files.exportProject();
        return path
          ? backend.request("POST", "/api/v1/local/export", {
              path,
              ...(document ? { project: document } : {}),
            })
          : null;
      }
      case "easyai:projects:exportBundle": {
        const projectId = id(args[0]);
        const revision = integer(args[1], 1);
        const programHash = args[2];
        if (
          typeof programHash !== "string" ||
          !/^[0-9a-f]{64}$/.test(programHash)
        )
          throw new Error("代码版本无效，请重新编译。");
        if (!this.files?.exportBundle) throw new Error("原生目录选择不可用。");
        const epoch = this.reportEpoch;
        const verify = async () => {
          if (epoch !== this.reportEpoch || this.backend() !== backend)
            throw new Error("工程或服务已变化，请重新导出。");
          const current = await backend.request<ProjectSession | null>(
            "GET",
            "/api/v1/local/session",
          );
          if (
            epoch !== this.reportEpoch ||
            this.backend() !== backend ||
            !current?.project ||
            current.readOnly ||
            current.project.projectId !== projectId ||
            current.project.revision !== revision
          )
            throw new Error("工程或版本已变化，请保存并重新编译后导出。");
        };
        await verify();
        const parentPath = await this.files.exportBundle();
        await verify();
        if (parentPath === null) return null;
        if (typeof parentPath !== "string" || !isAbsolute(parentPath))
          throw new Error("导出目标目录无效。");
        const result = await backend.request<BundleExportResult>(
          "POST",
          "/api/v1/local/export-bundle",
          {
            projectId,
            expectedRevision: revision,
            expectedProgramHash: programHash,
            parentPath,
          },
        );
        await verify();
        object(result, [
          "exported",
          "projectId",
          "projectRevision",
          "programHash",
          "codeHash",
          "bundleHash",
          "directoryName",
        ]);
        if (
          !result ||
          result.exported !== true ||
          result.projectId !== projectId ||
          result.projectRevision !== revision ||
          result.programHash !== programHash ||
          !/^[0-9a-f]{64}$/.test(result.codeHash) ||
          !/^[0-9a-f]{64}$/.test(result.bundleHash) ||
          !/^easyai-code-[0-9a-f-]{36}$/.test(result.directoryName)
        )
          throw new Error("导出结果与当前代码不一致，请检查所选目录。");
        return result;
      }
      case "easyai:projects:save": {
        const value = project(args[0]);
        return backend.request("PUT", `/api/v1/projects/${value.projectId}`, {
          project: value,
          expectedRevision: integer(args[1], 1),
        });
      }
      case "easyai:projects:compile": {
        const value = project(args[0]);
        return backend.request(
          "POST",
          `/api/v1/projects/${value.projectId}/compile`,
          { project: value, requestId: integer(args[1], 1) },
        );
      }
      case "easyai:runs:bind": {
        const value = object(args[0], [
          "projectId",
          "connectionId",
          "requestId",
          "expectedRevision",
          "expectedProgramHash",
          "probeRequestId",
          "runBase",
        ]);
        for (const key of [
          "projectId",
          "connectionId",
          "requestId",
          "probeRequestId",
        ])
          id(value[key]);
        integer(value.expectedRevision, 1);
        if (
          typeof value.expectedProgramHash !== "string" ||
          !/^[0-9a-f]{64}$/.test(value.expectedProgramHash) ||
          typeof value.runBase !== "string" ||
          value.runBase.length > 1024 ||
          !value.runBase.startsWith("/") ||
          /[\\\x00-\x1f\x7f]/.test(value.runBase) ||
          value.runBase
            .split("/")
            .slice(1)
            .some((part) => ["", ".", ".."].includes(part))
        )
          throw new Error("远端运行绑定无效。");
        return this.sessions.scoped(
          id(value.projectId),
          id(value.connectionId),
          (current) =>
            current.request(
              "POST",
              `/api/v1/projects/${value.projectId}/run-bindings`,
              value,
            ),
        );
      }
      case "easyai:runs:resume": {
        const runId = id(args[0]),
          projectId = id(args[1]),
          connectionId = id(args[2]);
        return this.sessions.scoped(projectId, connectionId, (current) =>
          current.request("POST", `/api/v1/runs/${runId}/resume`, {
            projectId,
            connectionId,
          }),
        );
      }
      case "easyai:runs:start": {
        const raw = object(args[0]);
        if (raw.runner === "ssh") {
          const value = object(raw, [
            "runner",
            "projectId",
            "bindingId",
            "expectedRevision",
            "expectedProgramHash",
            "idempotencyKey",
          ]);
          id(value.projectId);
          id(value.bindingId);
          id(value.idempotencyKey);
          integer(value.expectedRevision, 1);
          if (
            typeof value.expectedProgramHash !== "string" ||
            !/^[0-9a-f]{64}$/.test(value.expectedProgramHash)
          )
            throw new Error("编译摘要无效。");
          const projectId = id(value.projectId);
          const current = await backend.request<{
            project: { projectId: string } | null;
          } | null>("GET", "/api/v1/local/session");
          if (
            this.backend() !== backend ||
            current?.project?.projectId !== projectId
          )
            throw new Error("SSH_IDENTITY_PROJECT_CHANGED");
          const result = await backend.request(
            "POST",
            `/api/v1/projects/${projectId}/runs`,
            {
              runner: "ssh",
              bindingId: value.bindingId,
              expectedRevision: value.expectedRevision,
              expectedProgramHash: value.expectedProgramHash,
            },
            id(value.idempotencyKey),
          );
          const after = await backend.request<{
            project: { projectId: string } | null;
          } | null>("GET", "/api/v1/local/session");
          if (
            this.backend() !== backend ||
            after?.project?.projectId !== projectId
          )
            throw new Error("SSH_IDENTITY_PROJECT_CHANGED");
          return result;
        }
        const value = object(raw, [
          "projectId",
          "expectedRevision",
          "expectedProgramHash",
          "pythonSelectionId",
          "dataSelectionId",
          "idempotencyKey",
        ]);
        id(value.projectId);
        id(value.pythonSelectionId);
        id(value.dataSelectionId);
        id(value.idempotencyKey);
        integer(value.expectedRevision, 1);
        if (
          typeof value.expectedProgramHash !== "string" ||
          !/^[0-9a-f]{64}$/.test(value.expectedProgramHash)
        )
          throw new Error("编译摘要无效。");
        const request = value as unknown as Exclude<
          StartRun,
          { runner: "ssh" }
        >;
        return backend.request(
          "POST",
          `/api/v1/projects/${request.projectId}/runs`,
          {
            expectedRevision: request.expectedRevision,
            expectedProgramHash: request.expectedProgramHash,
            pythonSelectionId: request.pythonSelectionId,
            dataSelectionId: request.dataSelectionId,
          },
          request.idempotencyKey,
        );
      }
      case "easyai:runs:get":
        return backend.request("GET", `/api/v1/runs/${id(args[0])}`);
      case "easyai:runs:list": {
        const offset = integer(args[1]),
          limit = integer(args[2], 1);
        if (limit > 50) throw new Error("历史分页无效。");
        return backend.request(
          "GET",
          `/api/v1/projects/${id(args[0])}/runs?offset=${offset}&limit=${limit}`,
        );
      }
      case "easyai:packages:catalog":
        return backend.request("GET", "/api/v1/catalog/packages");
      case "easyai:packages:plan": {
        const value = object(args[0]);
        if (
          Object.keys(value).some(
            (key) =>
              ![
                "targetId",
                "remoteSession",
                "profileId",
                "packageIds",
                "ownedEnvironmentId",
                "newEnvironmentSpec",
              ].includes(key),
          ) ||
          (value.targetId !== "local" &&
            (typeof value.targetId !== "string" ||
              !uuid.test(value.targetId))) ||
          typeof value.profileId !== "string" ||
          !["teacher-existing", "easyai-cpu"].includes(value.profileId) ||
          !Array.isArray(value.packageIds) ||
          value.packageIds.length < 1 ||
          value.packageIds.length > 17 ||
          value.packageIds.some(
            (item) =>
              typeof item !== "string" || !/^[a-z][a-z0-9-]{0,63}$/.test(item),
          ) ||
          new Set(value.packageIds).size !== value.packageIds.length
        )
          throw new Error("安装计划输入无效。");
        let remoteSession:
          { projectId: string; connectionId: string } | undefined;
        if (value.targetId !== "local") {
          const scope = object(value.remoteSession, [
            "projectId",
            "connectionId",
          ]);
          remoteSession = {
            projectId: id(scope.projectId),
            connectionId: id(scope.connectionId),
          };
          const auth = (await this.sessions.invoke(
            "easyai:connections:current",
            [remoteSession.projectId, remoteSession.connectionId],
          )) as AuthenticatedConnection | null;
          if (!auth || auth.targetId !== value.targetId)
            throw Error("SSH_SESSION_INVALID");
        } else if (value.remoteSession != null) throw Error("安装目标不一致。");
        const owned =
          value.ownedEnvironmentId !== undefined &&
          value.ownedEnvironmentId !== null;
        const fresh =
          value.newEnvironmentSpec !== undefined &&
          value.newEnvironmentSpec !== null;
        if (owned === fresh) throw new Error("请选择单一受控环境。");
        let target: object;
        if (owned)
          target = { ownedEnvironmentId: id(value.ownedEnvironmentId) };
        else {
          const spec = object(value.newEnvironmentSpec, ["name"]);
          if (
            typeof spec.name !== "string" ||
            !/^[A-Za-z][A-Za-z0-9_-]{0,31}$/.test(spec.name)
          )
            throw new Error("新环境名称无效。");
          target = { newEnvironmentSpec: { name: spec.name } };
        }
        return backend.request("POST", "/api/v1/environments/install-plan", {
          targetId: value.targetId,
          ...(remoteSession ? { remoteSession } : {}),
          profileId: value.profileId,
          packageIds: [...value.packageIds],
          ...target,
        });
      }
      case "easyai:installJobs:reconcile": {
        const jobId = id(args[0]),
          scope = object(args[1], ["projectId", "connectionId"]);
        const session = {
          projectId: id(scope.projectId),
          connectionId: id(scope.connectionId),
        };
        if (typeof args[2] !== "boolean") throw Error("安装恢复输入无效。");
        const auth = await this.sessions.invoke("easyai:connections:current", [
          session.projectId,
          session.connectionId,
        ]);
        if (!auth) throw Error("SSH_SESSION_INVALID");
        return backend.request(
          "POST",
          `/api/v1/install-jobs/${jobId}/reconcile`,
          { session, cancel: args[2] },
        );
      }
      case "easyai:installJobs:confirm": {
        const value = object(args[0], [
          "planId",
          "planHash",
          "confirmed",
          "networkAcknowledged",
        ]);
        if (
          typeof value.planHash !== "string" ||
          !/^[a-f0-9]{64}$/.test(value.planHash) ||
          value.confirmed !== true ||
          value.networkAcknowledged !== true
        )
          throw new Error("请先明确核对安装计划。");
        return backend.request("POST", "/api/v1/install-jobs", {
          planId: id(value.planId),
          planHash: value.planHash,
          confirmed: true,
          networkAcknowledged: true,
        });
      }
      case "easyai:installJobs:get":
        return backend.request("GET", `/api/v1/install-jobs/${id(args[0])}`);
      case "easyai:installJobs:list":
        return backend.request("GET", "/api/v1/install-jobs");
      case "easyai:installJobs:report":
        return backend.request(
          "GET",
          `/api/v1/install-jobs/${id(args[0])}/report`,
        );
      case "easyai:installJobs:cancel":
        return backend.request(
          "POST",
          `/api/v1/install-jobs/${id(args[0])}/cancel`,
        );
      case "easyai:runs:cancel":
        return backend.request("POST", `/api/v1/runs/${id(args[0])}/cancel`);
      case "easyai:runs:report":
      case "easyai:runs:exportDiagnostic": {
        const epoch = this.reportEpoch;
        const runId = id(args[0]),
          seq = integer(args[1], 1);
        const route = `/api/v1/runs/${runId}/diagnostics/${seq}/report`;
        const report = safeReport(
          await backend.request("GET", route),
          runId,
          seq,
        );
        if (epoch !== this.reportEpoch) throw new Error("报告请求已过期。");
        if (channel === "easyai:runs:report") return report;
        if (!this.files?.exportDiagnostic)
          throw new Error("原生报告保存不可用。");
        const path = await this.files.exportDiagnostic();
        if (path === null) return { exported: false };
        if (epoch !== this.reportEpoch) throw new Error("报告请求已过期。");
        if (!isAbsolute(path)) throw new Error("报告目标无效。");
        // Recheck authorization and report identity after the native dialog awaited.
        const current = safeReport(
          await backend.request("GET", route),
          runId,
          seq,
        );
        if (epoch !== this.reportEpoch) throw new Error("报告请求已过期。");
        if (JSON.stringify(report) !== JSON.stringify(current))
          throw new Error("报告已变化，请重新预览。");
        await publishNewReport(
          path,
          JSON.stringify(current, null, 2) + "\n",
          () => {
            if (epoch !== this.reportEpoch) throw new Error("报告请求已过期。");
          },
        );
        return { exported: true };
      }
      case "easyai:runs:pauseArtifactSync":
      case "easyai:runs:resumeArtifactSync":
        return backend.request(
          "POST",
          `/api/v1/runs/${id(args[0])}/artifacts/sync/${channel.endsWith("pauseArtifactSync") ? "pause" : "resume"}`,
        );
      case "easyai:runs:source":
        return backend.request("GET", `/api/v1/runs/${id(args[0])}/source`);
      case "easyai:runs:artifacts":
        return backend.request("GET", `/api/v1/runs/${id(args[0])}/artifacts`);
      case "easyai:runs:logs":
        return backend.request(
          "GET",
          `/api/v1/runs/${id(args[0])}/logs?stdoutAfter=${integer(args[1])}&stderrAfter=${integer(args[2])}`,
        );
      case "easyai:runs:image":
        return backend.image(
          `/api/v1/runs/${id(args[0])}/artifacts/${id(args[1])}/content`,
        );
    }
  }
  subscribe(subscriptionId: unknown, runId: unknown, after: unknown): void {
    const key = id(subscriptionId);
    const run = id(runId);
    const cursor = integer(after);
    const backend = this.backend();
    if (!backend) throw new Error("本地服务未就绪。");
    this.clearSubscriptions(); // One visible run stream per window; tab changes cannot multiply readers.
    const controller = new AbortController();
    this.subscriptions.set(key, controller);
    const send = (message: SubscriptionMessage) => {
      if (!controller.signal.aborted) this.send(message);
    };
    void backend
      .events(
        run,
        cursor,
        (event) => send({ subscriptionId: key, kind: "event", event }),
        (state, message) =>
          send({
            subscriptionId: key,
            kind: "connection",
            state,
            ...(message ? { message } : {}),
          }),
        controller.signal,
      )
      .catch(() =>
        send({
          subscriptionId: key,
          kind: "connection",
          state: "error",
          message: "事件连接失败。",
        }),
      )
      .finally(() => {
        if (this.subscriptions.get(key) === controller)
          this.subscriptions.delete(key);
      });
  }
  unsubscribe(subscriptionId: unknown): void {
    const key = id(subscriptionId);
    this.subscriptions.get(key)?.abort();
    this.subscriptions.delete(key);
  }
  dispose(): void {
    this.sourceEpoch++;
    this.sourceReceipt = undefined;
    this.reportEpoch += 1;
    this.transfers.invalidate();
    this.sessions.invalidate();
    this.identity.invalidate();
    this.clearSubscriptions();
  }
  private clearSubscriptions(): void {
    for (const controller of this.subscriptions.values()) controller.abort();
    this.subscriptions.clear();
  }
}
