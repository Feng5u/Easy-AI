import { isIP } from "node:net";
import { domainToASCII } from "node:url";
import type { Backend } from "./backend.mjs";
import type {
  HostKeyObservation,
  IdentityResult,
  SshEndpoint,
} from "./bridge.js";

const uuid = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
const fingerprint = /^SHA256:[A-Za-z0-9+/]{43}$/;
function identifier(value: unknown): string {
  if (typeof value !== "string" || !uuid.test(value))
    throw new Error("SSH_IDENTITY_REQUEST_INVALID");
  return value;
}
function endpoint(value: unknown): SshEndpoint {
  if (!value || typeof value !== "object" || Array.isArray(value))
    throw new Error("SSH_IDENTITY_REQUEST_INVALID");
  const record = value as Record<string, unknown>;
  if (
    Object.keys(record).length !== 2 ||
    !Object.hasOwn(record, "host") ||
    !Object.hasOwn(record, "port") ||
    typeof record.host !== "string" ||
    !record.host ||
    record.host.length > 253 ||
    /[\s/@\\]/u.test(record.host) ||
    !Number.isSafeInteger(record.port) ||
    Number(record.port) < 1 ||
    Number(record.port) > 65535
  )
    throw new Error("SSH_IDENTITY_REQUEST_INVALID");
  let host = record.host;
  if (isIP(host) === 6) {
    host = new URL(`http://[${host}]/`).hostname.slice(1, -1);
  } else if (isIP(host) !== 4) {
    if (/^[0-9.]+$/.test(host)) throw new Error("SSH_IDENTITY_REQUEST_INVALID");
    host = domainToASCII(
      host.endsWith(".") ? host.slice(0, -1) : host,
    ).toLowerCase();
    if (
      !host ||
      host.length > 253 ||
      isIP(host) ||
      host
        .split(".")
        .some((label) => !/^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$/.test(label))
    )
      throw new Error("SSH_IDENTITY_REQUEST_INVALID");
  }
  return { host, port: Number(record.port) };
}
interface Operation {
  endpoint: SshEndpoint;
  projectId: string;
  requestId: string;
  backend: Backend;
  observation?: HostKeyObservation;
  confirming?: boolean;
}
export class IdentityWorkflow {
  private active?: Operation;
  constructor(private backend: () => Backend | undefined) {}
  trustedTarget(projectId: string, requestId: string) {
    const operation = this.active;
    if (
      !operation ||
      operation.projectId !== projectId ||
      operation.requestId !== requestId ||
      this.backend() !== operation.backend ||
      operation.observation?.trustState !== "trusted"
    )
      throw new Error("SSH_IDENTITY_CONFIRMATION_STALE");
    return {
      backend: operation.backend,
      endpoint: { ...operation.endpoint },
      fingerprint: operation.observation.fingerprint,
    };
  }
  private cancelOperation(operation: Operation): Promise<void> {
    return operation.backend
      .request("POST", "/api/v1/connections/identity/cancel", {
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
  private async verify(operation: Operation): Promise<void> {
    if (this.active !== operation || this.backend() !== operation.backend)
      throw new Error("SSH_IDENTITY_CANCELLED");
    const current = await operation.backend.request<{
      project: { projectId: string } | null;
    } | null>("GET", "/api/v1/local/session");
    if (
      this.active !== operation ||
      this.backend() !== operation.backend ||
      current?.project?.projectId !== operation.projectId
    )
      throw new Error("SSH_IDENTITY_PROJECT_CHANGED");
  }
  private result(value: IdentityResult, operation: Operation): IdentityResult {
    const observed = value?.observation;
    if (
      value?.projectId !== operation.projectId ||
      value?.requestId !== operation.requestId ||
      !observed ||
      !["unknown", "changed", "trusted"].includes(observed.trustState) ||
      typeof observed.algorithm !== "string" ||
      observed.algorithm.length > 64 ||
      !fingerprint.test(observed.fingerprint) ||
      (observed.trustState === "unknown" &&
        (typeof observed.challengeId !== "string" ||
          !uuid.test(observed.challengeId))) ||
      (observed.trustState === "changed" &&
        (typeof observed.previousFingerprint !== "string" ||
          !fingerprint.test(observed.previousFingerprint)))
    )
      throw new Error("SSH_IDENTITY_RESPONSE_INVALID");
    const target = endpoint(observed.endpoint);
    if (
      target.host !== operation.endpoint.host ||
      target.port !== operation.endpoint.port
    )
      throw new Error("SSH_IDENTITY_RESPONSE_INVALID");
    return value;
  }
  async invoke(channel: string, args: unknown[]): Promise<unknown> {
    const count =
      channel === "easyai:connections:probe" ||
      channel === "easyai:connections:confirm"
        ? 3
        : 2;
    if (args.length !== count) throw new Error("SSH_IDENTITY_REQUEST_INVALID");
    const projectId = identifier(args[0]),
      requestId = identifier(args[1]);
    if (channel === "easyai:connections:cancel") {
      const operation = this.active;
      if (
        operation?.projectId === projectId &&
        operation.requestId === requestId
      ) {
        this.active = undefined;
        await this.cancelOperation(operation);
      }
      return;
    }
    if (channel === "easyai:connections:probe") {
      const target = endpoint(args[2]);
      const backend = this.backend();
      if (!backend) throw new Error("SSH_BACKEND_UNAVAILABLE");
      this.invalidate();
      const operation: Operation = {
        projectId,
        requestId,
        backend,
        endpoint: target,
      };
      this.active = operation;
      try {
        await this.verify(operation);
        const result = this.result(
          await backend.request<IdentityResult>(
            "POST",
            "/api/v1/connections/identity/probe",
            { projectId, requestId, endpoint: target },
          ),
          operation,
        );
        await this.verify(operation);
        operation.observation = result.observation;
        return result;
      } catch (error) {
        if (this.active === operation) this.invalidate();
        throw this.sanitized(error);
      }
    }
    if (channel !== "easyai:connections:confirm")
      throw new Error("SSH_IDENTITY_REQUEST_INVALID");
    const operation = this.active;
    const observed = operation?.observation;
    if (
      !operation ||
      operation.projectId !== projectId ||
      operation.requestId !== requestId ||
      !observed ||
      observed.trustState !== "unknown" ||
      operation.confirming ||
      args[2] !== observed.fingerprint
    )
      throw new Error("SSH_IDENTITY_CONFIRMATION_STALE");
    operation.confirming = true;
    try {
      await this.verify(operation);
      const result = this.result(
        await operation.backend.request<IdentityResult>(
          "POST",
          "/api/v1/connections/identity/confirm",
          {
            projectId,
            requestId,
            confirmation: {
              challengeId: observed.challengeId,
              fingerprint: observed.fingerprint,
            },
          },
        ),
        operation,
      );
      await this.verify(operation);
      if (
        result.observation.trustState !== "trusted" ||
        result.observation.fingerprint !== observed.fingerprint ||
        result.observation.endpoint.host !== observed.endpoint.host ||
        result.observation.endpoint.port !== observed.endpoint.port
      )
        throw new Error("SSH_IDENTITY_RESPONSE_INVALID");
      operation.observation = result.observation;
      return result;
    } catch (error) {
      if (this.active === operation) this.invalidate();
      throw this.sanitized(error);
    } finally {
      operation.confirming = false;
    }
  }
  private sanitized(error: unknown): Error {
    const code =
      error instanceof Error && /^SSH_[A-Z_]{1,80}$/.test(error.message)
        ? error.message
        : "SSH_IDENTITY_FAILED";
    return new Error(code);
  }
}
