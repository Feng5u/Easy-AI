import { IdentityWorkflow } from "./identity-workflow.mjs";
import type { Backend } from "./backend.mjs";
import type {
  ProjectDocument,
  SelectionKind,
  StartRun,
  SubscriptionMessage,
} from "./bridge.js";

const uuid = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
export const WORKFLOW_CHANNELS = [
  "easyai:connections:probe",
  "easyai:connections:confirm",
  "easyai:connections:cancel",
  "easyai:selections:pick",
  "easyai:projects:current",
  "easyai:projects:open",
  "easyai:projects:create",
  "easyai:projects:import",
  "easyai:projects:export",
  "easyai:projects:save",
  "easyai:projects:compile",
  "easyai:runs:start",
  "easyai:runs:list",
  "easyai:runs:get",
  "easyai:runs:cancel",
  "easyai:runs:source",
  "easyai:runs:logs",
  "easyai:runs:artifacts",
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
    },
  ) {
    this.identity = new IdentityWorkflow(backend);
  }
  async invoke(channel: string, args: unknown[]): Promise<unknown> {
    if (
      channel === "easyai:connections:probe" ||
      channel === "easyai:connections:confirm" ||
      channel === "easyai:connections:cancel"
    )
      return this.identity.invoke(channel, args);
    const backend = this.backend();
    if (!backend) throw new Error("本地服务未就绪。");
    const counts: Record<string, number> = {
      "easyai:selections:pick": 1,
      "easyai:projects:current": 0,
      "easyai:projects:open": 1,
      "easyai:projects:create": 2,
      "easyai:projects:import": 0,
      "easyai:projects:export": 0,
      "easyai:projects:save": 2,
      "easyai:projects:compile": 2,
      "easyai:runs:start": 1,
      "easyai:runs:list": 3,
      "easyai:runs:get": 1,
      "easyai:runs:cancel": 1,
      "easyai:runs:source": 1,
      "easyai:runs:logs": 3,
      "easyai:runs:artifacts": 1,
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
    )
      this.identity.invalidate();
    switch (channel) {
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
      case "easyai:runs:start": {
        const value = object(args[0], [
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
        const request = value as unknown as StartRun;
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
      case "easyai:runs:cancel":
        return backend.request("POST", `/api/v1/runs/${id(args[0])}/cancel`);
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
    this.identity.invalidate();
    this.clearSubscriptions();
  }
  private clearSubscriptions(): void {
    for (const controller of this.subscriptions.values()) controller.abort();
    this.subscriptions.clear();
  }
}
