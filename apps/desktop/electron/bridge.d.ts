import type { AuthenticatedConnection } from "../../../packages/contracts/types/AuthenticatedConnection.js";
import type { EnvironmentCatalog } from "../../../packages/contracts/types/EnvironmentCatalog.js";
import type { EnvironmentDiscoveryRequest } from "../../../packages/contracts/types/EnvironmentDiscoveryRequest.js";
import type { EnvironmentProbeRequest } from "../../../packages/contracts/types/EnvironmentProbeRequest.js";
import type { EnvironmentProbeResult } from "../../../packages/contracts/types/EnvironmentProbeResult.js";
import type { EnvironmentRequest } from "../../../packages/contracts/types/EnvironmentRequest.js";
export type {
  AuthenticatedConnection,
  EnvironmentCatalog,
  EnvironmentDiscoveryRequest,
  EnvironmentProbeRequest,
  EnvironmentProbeResult,
  EnvironmentRequest,
};
import type { HostKeyObservation } from "../../../packages/contracts/types/HostKeyObservation.js";
import type { SshEndpoint } from "../../../packages/contracts/types/SshEndpoint.js";
import type { IdentityResult } from "../../../packages/contracts/types/IdentityResult.js";
export type { HostKeyObservation, SshEndpoint, IdentityResult };
import type { ProjectDocument } from "../../../packages/contracts/types/ProjectDocument.js";
import type { CompileResult } from "../../../packages/contracts/types/CompileResult.js";
import type { ProjectSession } from "../../../packages/contracts/types/ProjectSession.js";
import type { SelectionResult } from "../../../packages/contracts/types/SelectionResult.js";
import type { Run } from "../../../packages/contracts/types/Run.js";
import type { Event } from "../../../packages/contracts/types/Event.js";
import type { ArtifactRecord } from "../../../packages/contracts/types/ArtifactRecord.js";
import type { RunLogs } from "../../../packages/contracts/types/RunLogs.js";
import type { RunSource } from "../../../packages/contracts/types/RunSource.js";
export type {
  ProjectDocument,
  CompileResult,
  ProjectSession,
  SelectionResult,
  Run,
  Event,
  ArtifactRecord,
  RunLogs,
  RunSource,
};
export type SelectionKind = "project" | "python" | "data";
export interface StartRun {
  projectId: string;
  expectedRevision: number;
  expectedProgramHash: string;
  pythonSelectionId: string;
  dataSelectionId: string;
  idempotencyKey: string;
}
export type ConnectionState = "connected" | "reconnecting" | "closed" | "error";
export interface DesktopAPI {
  connections: {
    authenticate(
      projectId: string,
      requestId: string,
      identityRequestId: string,
      username: string,
      password: string,
    ): Promise<AuthenticatedConnection>;
    cancelAuth(projectId: string, requestId: string): Promise<void>;
    close(projectId: string, connectionId: string): Promise<void>;
    current(
      projectId: string,
      connectionId: string,
    ): Promise<AuthenticatedConnection | null>;
    probe(
      projectId: string,
      requestId: string,
      endpoint: SshEndpoint,
    ): Promise<IdentityResult>;
    confirm(
      projectId: string,
      requestId: string,
      fingerprint: string,
    ): Promise<IdentityResult>;
    cancel(projectId: string, requestId: string): Promise<void>;
  };
  environments: {
    discover(request: EnvironmentDiscoveryRequest): Promise<EnvironmentCatalog>;
    probe(request: EnvironmentProbeRequest): Promise<EnvironmentProbeResult>;
    cancel(request: EnvironmentRequest): Promise<void>;
  };
  status: {
    get(): Promise<{ ready: boolean; message: string }>;
    subscribe(
      onStatus: (status: { ready: boolean; message: string }) => void,
    ): () => void;
  };
  selections: { pick(kind: SelectionKind): Promise<SelectionResult | null> };
  projects: {
    setDirty(dirty: boolean): Promise<void>;
    current(): Promise<ProjectSession | null>;
    open(selectionId: string): Promise<ProjectSession>;
    create(
      selectionId: string,
      name: string,
      template?: "mnist-cnn" | "blank",
    ): Promise<ProjectSession>;
    importProject(): Promise<ProjectSession | null>;
    exportProject(
      project?: ProjectDocument,
    ): Promise<{ exported: boolean } | null>;
    save(
      project: ProjectDocument,
      expectedRevision: number,
    ): Promise<ProjectSession>;
    compile(
      project: ProjectDocument,
      requestId: number,
    ): Promise<CompileResult>;
  };
  runs: {
    list(projectId: string, offset: number, limit: number): Promise<Run[]>;
    start(request: StartRun): Promise<Run>;
    get(runId: string): Promise<Run>;
    cancel(runId: string): Promise<Run>;
    source(runId: string): Promise<RunSource>;
    logs(
      runId: string,
      stdoutAfter: number,
      stderrAfter: number,
    ): Promise<RunLogs>;
    artifacts(runId: string): Promise<ArtifactRecord[]>;
    image(runId: string, artifactId: string): Promise<{ dataUrl: string }>;
    subscribe(
      runId: string,
      after: number,
      onEvent: (event: Event) => void,
      onConnection: (state: ConnectionState, message?: string) => void,
    ): () => void;
  };
}
export type SubscriptionMessage =
  | { subscriptionId: string; kind: "event"; event: Event }
  | {
      subscriptionId: string;
      kind: "connection";
      state: ConnectionState;
      message?: string;
    };
