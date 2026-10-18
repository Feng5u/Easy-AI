import type { Backend } from "./backend.mjs";
import type { IdentityWorkflow } from "./identity-workflow.mjs";
import { readSelectedPrivateKey } from "./private-key-file.mjs";
import type {
  AuthenticatedConnection,
  EnvironmentCatalog,
  EnvironmentDiscoveryRequest,
  EnvironmentProbeRequest,
  EnvironmentProbeResult,
  EnvironmentRequest,
} from "./bridge.js";

const uuid = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
function id(value: unknown): string {
  if (typeof value !== "string" || !uuid.test(value))
    throw new Error("SSH_REQUEST_INVALID");
  return value;
}
function object(value: unknown): Record<string, unknown> {
  if (!value || typeof value !== "object" || Array.isArray(value))
    throw new Error("SSH_REQUEST_INVALID");
  return value as Record<string, unknown>;
}
function remotePath(value: unknown): string {
  if (
    typeof value !== "string" ||
    value.length < 2 ||
    value.length > 1024 ||
    !value.startsWith("/") ||
    /[\x00-\x1f\x7f\\]/.test(value) ||
    value.split("/").includes("..")
  )
    throw new Error("SSH_REQUEST_INVALID");
  return value;
}
interface Operation {
  projectId: string;
  targetId?: string;
  requestId: string;
  identityRequestId: string;
  backend: Backend;
  cancel: Promise<void>;
  resolveCancel(): void;
  info?: AuthenticatedConnection;
  environment?: {
    requestId: string;
    cancel: Promise<void>;
    resolveCancel(): void;
  };
  catalog?: EnvironmentCatalog;
}
function cancellation() {
  let resolveCancel!: () => void;
  const cancel = new Promise<void>((resolve) => {
    resolveCancel = resolve;
  });
  return { cancel, resolveCancel };
}
export class SessionWorkflow {
  private active?: Operation;
  constructor(
    private backend: () => Backend | undefined,
    private identity: IdentityWorkflow,
    private choosePrivateKey?: () => Promise<string | null>,
  ) {}
  private async race<T>(operation: Operation, promise: Promise<T>): Promise<T> {
    return Promise.race([
      promise,
      operation.cancel.then(() => {
        throw new Error("SSH_AUTH_CANCELLED");
      }),
    ]);
  }
  private cancelOperation(operation: Operation): Promise<void> {
    operation.resolveCancel();
    operation.environment?.resolveCancel();
    return operation.backend
      .request("POST", "/api/v1/connections/auth/cancel", {
        projectId: operation.projectId,
        requestId: operation.requestId,
      })
      .then(() => undefined);
  }
  invalidate(): void {
    const operation = this.active;
    this.active = undefined;
    if (operation) void this.cancelOperation(operation).catch(() => undefined);
  }
  invalidateTarget(targetId: string): void {
    if (this.active?.targetId === targetId) this.invalidate();
  }
  cancelIdentity(projectId: unknown, requestId: unknown): void {
    const operation = this.active;
    if (
      operation?.projectId === projectId &&
      operation?.identityRequestId === requestId
    )
      this.invalidate();
  }
  private async verify(
    operation: Operation,
    authenticated = false,
  ): Promise<void> {
    if (this.active !== operation || this.backend() !== operation.backend)
      throw new Error("SSH_AUTH_CANCELLED");
    const current = await this.race(
      operation,
      operation.backend.request<{
        project: { projectId: string } | null;
      } | null>("GET", "/api/v1/local/session"),
    );
    if (
      this.active !== operation ||
      this.backend() !== operation.backend ||
      current?.project?.projectId !== operation.projectId
    )
      throw new Error("SSH_IDENTITY_PROJECT_CHANGED");
    if (authenticated) {
      const info = operation.info!;
      const value = await this.race(
        operation,
        operation.backend.request<AuthenticatedConnection | null>(
          "GET",
          `/api/v1/connections/session?projectId=${operation.projectId}&connectionId=${info.scope.connectionId}`,
        ),
      );
      if (
        !value ||
        JSON.stringify(value.scope) !== JSON.stringify(info.scope) ||
        value.requestId !== operation.requestId ||
        value.targetId !== info.targetId ||
        value.targetRevision !== info.targetRevision ||
        value.authenticated !== true ||
        value.method !== info.method ||
        (value.method !== "password" && value.method !== "private_key")
      )
        throw new Error("SSH_CONNECTION_INVALID");
      if (this.active !== operation || this.backend() !== operation.backend)
        throw new Error("SSH_AUTH_CANCELLED");
    }
  }
  async scoped<T>(
    projectId: string,
    connectionId: string,
    action: (backend: Backend) => Promise<T>,
  ): Promise<T> {
    const operation = this.active;
    if (
      !operation ||
      operation.projectId !== projectId ||
      operation.info?.scope.connectionId !== connectionId
    )
      throw new Error("SSH_CONNECTION_INVALID");
    await this.verify(operation, true);
    const value = await this.race(operation, action(operation.backend));
    await this.verify(operation, true);
    return value;
  }
  async invoke(channel: string, args: unknown[]): Promise<unknown> {
    if (
      channel === "easyai:connections:authenticate" ||
      channel === "easyai:connections:authenticateKey"
    )
      return this.authenticate(args, channel.endsWith("authenticateKey"));
    if (channel.startsWith("easyai:environments:"))
      return this.environment(channel, args);
    if (args.length !== 2) throw new Error("SSH_REQUEST_INVALID");
    const projectId = id(args[0]),
      requestId = id(args[1]);
    const operation = this.active;
    if (!operation || operation.projectId !== projectId)
      return channel === "easyai:connections:current" ? null : undefined;
    if (channel === "easyai:connections:cancelAuth") {
      if (operation.requestId === requestId) this.invalidate();
      return;
    }
    if (operation.info?.scope.connectionId !== requestId)
      return channel === "easyai:connections:current" ? null : undefined;
    if (channel === "easyai:connections:close") {
      this.invalidate();
      return;
    }
    if (channel !== "easyai:connections:current")
      throw new Error("SSH_REQUEST_INVALID");
    try {
      await this.verify(operation, true);
      return operation.info;
    } catch {
      if (this.active === operation) this.invalidate();
      return null;
    }
  }
  private async authenticate(
    args: unknown[],
    usingKey = false,
  ): Promise<AuthenticatedConnection> {
    const secretIsString = typeof args[4] === "string";
    let password = typeof args[4] === "string" ? args[4] : "";
    let key = "";
    args[4] = "";
    let body:
      | {
          request: Record<string, unknown>;
          password?: string;
          privateKey?: string;
          passphrase?: string;
        }
      | undefined;
    let operation: Operation | undefined;
    try {
      if (
        ![5, 6].includes(args.length) ||
        !secretIsString ||
        (!usingKey && !password) ||
        password.length > 1024
      )
        throw new Error("SSH_REQUEST_INVALID");
      const projectId = id(args[0]),
        requestId = id(args[1]),
        identityRequestId = id(args[2]);
      const username = args[3];
      if (
        typeof username !== "string" ||
        !username ||
        username.length > 128 ||
        /[\x00-\x1f\x7f]/.test(username)
      )
        throw new Error("SSH_REQUEST_INVALID");
      let profile: { targetId: string; targetRevision: number } | undefined;
      if (args.length === 6) {
        const target = object(args[5]);
        if (
          Object.keys(target).length !== 2 ||
          !Object.hasOwn(target, "targetId") ||
          !Object.hasOwn(target, "expectedRevision") ||
          !Number.isSafeInteger(target.expectedRevision) ||
          Number(target.expectedRevision) < 1
        )
          throw new Error("SSH_REQUEST_INVALID");
        profile = {
          targetId: id(target.targetId),
          targetRevision: Number(target.expectedRevision),
        };
      }
      if (this.active) throw new Error("SSH_AUTH_BUSY");
      const target = this.identity.trustedTarget(projectId, identityRequestId);
      operation = {
        projectId,
        requestId,
        identityRequestId,
        backend: target.backend,
        targetId: profile?.targetId,
        ...cancellation(),
      };
      this.active = operation;
      await this.verify(operation);
      if (usingKey) {
        if (!this.choosePrivateKey)
          throw new Error("SSH_PRIVATE_KEY_UNAVAILABLE");
        const selected = await this.race(operation, this.choosePrivateKey());
        await this.verify(operation);
        if (!selected) throw new Error("SSH_AUTH_CANCELLED");
        key = await readSelectedPrivateKey(selected);
        await this.verify(operation);
      }
      body = {
        request: {
          projectId,
          requestId,
          identityRequestId,
          username,
          expectedFingerprint: target.fingerprint,
          ...profile,
        },
        ...(usingKey
          ? { privateKey: key, passphrase: password }
          : { password }),
      };
      key = "";
      const value = await this.race(
        operation,
        operation.backend.request<AuthenticatedConnection>(
          "POST",
          usingKey
            ? "/api/v1/connections/auth/private-key"
            : "/api/v1/connections/auth/password",
          body,
        ),
      );
      password = "";
      if (usingKey) {
        body.privateKey = "";
        body.passphrase = "";
      } else body.password = "";
      await this.verify(operation);
      if (
        !value ||
        value.authenticated !== true ||
        value.method !== (usingKey ? "private_key" : "password") ||
        value.projectId !== projectId ||
        value.requestId !== requestId ||
        value.identityRequestId !== identityRequestId ||
        value.username !== username ||
        (profile &&
          (value.targetId !== profile.targetId ||
            value.targetRevision !== profile.targetRevision)) ||
        value.scope?.projectId !== projectId ||
        !uuid.test(value.scope?.connectionId ?? "") ||
        value.scope.hostFingerprint !== target.fingerprint ||
        value.scope.endpoint?.host !== target.endpoint.host ||
        value.scope.endpoint.port !== target.endpoint.port ||
        !Number.isInteger(value.expiresInSeconds) ||
        value.expiresInSeconds < 1 ||
        value.expiresInSeconds > 300
      )
        throw new Error("SSH_AUTH_RESPONSE_INVALID");
      operation.info = value;
      await this.verify(operation, true);
      return value;
    } catch {
      if (operation && this.active === operation) this.invalidate();
      // Never forward SDK/fetch messages: even an apparent error code may contain a password.
      throw new Error("SSH_AUTH_FAILED");
    } finally {
      password = "";
      key = "";
      if (body) {
        if (usingKey) {
          body.privateKey = "";
          body.passphrase = "";
        } else body.password = "";
      }
    }
  }
  private async environment(
    channel: string,
    args: unknown[],
  ): Promise<unknown> {
    if (args.length !== 1) throw new Error("SSH_REQUEST_INVALID");
    const input = object(args[0]);
    const projectId = id(input.projectId),
      connectionId = id(input.connectionId),
      requestId = id(input.requestId);
    const operation = this.active;
    if (
      !operation?.info ||
      operation.projectId !== projectId ||
      operation.info.scope.connectionId !== connectionId
    )
      throw new Error("SSH_CONNECTION_INVALID");
    const base: EnvironmentRequest = { projectId, connectionId, requestId };
    if (channel === "easyai:environments:cancel") {
      if (
        Object.keys(input).some(
          (k) => !["projectId", "connectionId", "requestId"].includes(k),
        )
      )
        throw new Error("SSH_REQUEST_INVALID");
      const running = operation.environment?.requestId === requestId;
      if (running && this.active === operation) this.invalidate();
      await operation.backend.request(
        "POST",
        "/api/v1/environments/cancel",
        base,
      );
      return;
    }
    let body: EnvironmentDiscoveryRequest | EnvironmentProbeRequest;
    const discovery = channel === "easyai:environments:discover";
    if (discovery) {
      if (
        Object.keys(input).some(
          (k) =>
            ![
              "projectId",
              "connectionId",
              "requestId",
              "condaPath",
              "pythonPath",
            ].includes(k),
        ) ||
        (input.condaPath != null && input.pythonPath != null)
      )
        throw new Error("SSH_REQUEST_INVALID");
      body = {
        ...base,
        ...(input.condaPath != null
          ? { condaPath: remotePath(input.condaPath) }
          : {}),
        ...(input.pythonPath != null
          ? { pythonPath: remotePath(input.pythonPath) }
          : {}),
      };
    } else {
      if (
        channel !== "easyai:environments:probe" ||
        Object.keys(input).some(
          (k) =>
            ![
              "projectId",
              "connectionId",
              "requestId",
              "environmentId",
              "device",
              "dataset",
            ].includes(k),
        )
      )
        throw new Error("SSH_REQUEST_INVALID");
      const environmentId = id(input.environmentId);
      if (
        !operation.catalog?.environments.some(
          (e) => e.environmentId === environmentId,
        )
      )
        throw new Error("ENVIRONMENT_SELECTION_STALE");
      const device = input.device ?? "cpu";
      if (device !== "cpu" && device !== "cuda" && device !== "mps")
        throw new Error("SSH_REQUEST_INVALID");
      body = { ...base, environmentId, device };
      if (input.dataset != null) {
        const dataset = object(input.dataset);
        if (
          Object.keys(dataset).length !== 2 ||
          !["MNIST", "FashionMNIST", "CIFAR10"].includes(String(dataset.name))
        )
          throw new Error("SSH_REQUEST_INVALID");
        body.dataset = {
          name: dataset.name as "MNIST" | "FashionMNIST" | "CIFAR10",
          dataRoot: remotePath(dataset.dataRoot),
        };
      }
    }
    if (operation.environment) throw new Error("ENVIRONMENT_BUSY");
    const pending = { requestId, ...cancellation() };
    operation.environment = pending;
    if (discovery) operation.catalog = undefined;
    try {
      await this.verify(operation, true);
      const value = await this.race(
        operation,
        Promise.race([
          operation.backend.request<
            EnvironmentCatalog | EnvironmentProbeResult
          >(
            "POST",
            `/api/v1/environments/${discovery ? "discover" : "probe"}`,
            body,
          ),
          pending.cancel.then(() => {
            throw new Error("ENVIRONMENT_CANCELLED");
          }),
        ]),
      );
      await this.verify(operation, true);
      if (
        operation.environment !== pending ||
        !value ||
        value.projectId !== projectId ||
        value.connectionId !== connectionId ||
        value.requestId !== requestId ||
        JSON.stringify(value.scope) !== JSON.stringify(operation.info.scope)
      )
        throw new Error("ENVIRONMENT_RESPONSE_INVALID");
      if (discovery) {
        const catalog = value as EnvironmentCatalog;
        if (
          !Array.isArray(catalog.environments) ||
          catalog.environments.length > 64 ||
          new Set(catalog.environments.map((e) => e.environmentId)).size !==
            catalog.environments.length ||
          catalog.environments.some(
            (e) =>
              !uuid.test(e.environmentId) ||
              !["conda", "python"].includes(e.kind) ||
              e.readOnly !== true ||
              !remotePath(e.location),
          )
        )
          throw new Error("ENVIRONMENT_RESPONSE_INVALID");
        operation.catalog = catalog;
      } else {
        const result = value as EnvironmentProbeResult,
          probe = body as EnvironmentProbeRequest;
        const selected = operation.catalog!.environments.find(
          (e) => e.environmentId === probe.environmentId,
        )!;
        if (
          result.environmentId !== probe.environmentId ||
          result.report?.nonce !== requestId ||
          result.report.tensor?.device !== probe.device ||
          JSON.stringify(
            result.report.dataset
              ? {
                  name: result.report.dataset.name,
                  dataRoot: result.report.dataset.dataRoot,
                }
              : null,
          ) !== JSON.stringify(probe.dataset ?? null) ||
          (selected.kind === "python"
            ? result.report.python?.executable
            : result.report.python?.prefix) !== selected.location
        )
          throw new Error("ENVIRONMENT_RESPONSE_INVALID");
      }
      return value;
    } catch {
      if (this.active === operation) this.invalidate();
      throw new Error("ENVIRONMENT_FAILED");
    } finally {
      if (operation.environment === pending) operation.environment = undefined;
    }
  }
}
