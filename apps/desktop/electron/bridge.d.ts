import type { TransferHistory } from "../../../packages/contracts/types/TransferHistory.js";
import type { PackageCatalog } from "../../../packages/contracts/types/PackageCatalog.js";
import type { InstallPlanRequest } from "../../../packages/contracts/types/InstallPlanRequest.js";
import type { InstallPlan } from "../../../packages/contracts/types/InstallPlan.js";
import type { InstallConfirmation } from "../../../packages/contracts/types/InstallConfirmation.js";
import type { InstallJob } from "../../../packages/contracts/types/InstallJob.js";
import type {
  InstallJobHistory,
  InstallJobSummary,
} from "../../../packages/contracts/types/InstallJobHistory.js";
import type { InstallJobReport } from "../../../packages/contracts/types/InstallJobReport.js";
import type { InstallSourceSelection } from "../../../packages/contracts/types/InstallSourceSelection.js";
import type { InstallSourcePreview } from "../../../packages/contracts/types/InstallSourcePreview.js";
import type { InstallSourceConfirmation } from "../../../packages/contracts/types/InstallSourceConfirmation.js";
import type { InstallSourceResult } from "../../../packages/contracts/types/InstallSourceResult.js";
export type {
  PackageCatalog,
  InstallPlanRequest,
  InstallPlan,
  InstallConfirmation,
  InstallJob,
  InstallJobHistory,
  InstallJobReport,
  InstallJobSummary,
  InstallSourceSelection,
  InstallSourcePreview,
  InstallSourceConfirmation,
  InstallSourceResult,
};
import type { DiagnosticReport } from "../../../packages/contracts/types/DiagnosticReport.js";
import type { BundleExportResult } from "../../../packages/contracts/types/BundleExportResult.js";
import type { TransferPlanRequest } from "../../../packages/contracts/types/TransferPlanRequest.js";
import type { TransferPlan } from "../../../packages/contracts/types/TransferPlan.js";
import type { TransferConfirmation } from "../../../packages/contracts/types/TransferConfirmation.js";
import type { TransferJob } from "../../../packages/contracts/types/TransferJob.js";
export type {
  TransferPlanRequest,
  TransferPlan,
  TransferConfirmation,
  TransferJob,
};
export type { BundleExportResult };
export type { DiagnosticReport };
import type { ConnectionProfile } from "../../../packages/contracts/types/ConnectionProfile.js";
import type { ConnectionProfileInput } from "../../../packages/contracts/types/ConnectionProfileInput.js";
import type { ConnectionProfileUpdate } from "../../../packages/contracts/types/ConnectionProfileUpdate.js";
import type { ConnectionTargetReference } from "../../../packages/contracts/types/ConnectionTargetReference.js";
export type {
  ConnectionProfile,
  ConnectionProfileInput,
  ConnectionProfileUpdate,
  ConnectionTargetReference,
};
import type { LocalPreflightRequest } from "../../../packages/contracts/types/LocalPreflightRequest.js";
import type { LocalPreflightResult } from "../../../packages/contracts/types/LocalPreflightResult.js";
export type { LocalPreflightRequest, LocalPreflightResult };
import type { RemoteBinding } from "../../../packages/contracts/types/RemoteBinding.js";
import type { RemoteBindingRequest } from "../../../packages/contracts/types/RemoteBindingRequest.js";
export type { RemoteBinding, RemoteBindingRequest };
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
export interface LocalStartRun {
  projectId: string;
  expectedRevision: number;
  expectedProgramHash: string;
  pythonSelectionId: string;
  dataSelectionId: string;
  idempotencyKey: string;
}
export interface SshStartRun {
  runner: "ssh";
  projectId: string;
  bindingId: string;
  expectedRevision: number;
  expectedProgramHash: string;
  idempotencyKey: string;
}
export type StartRun = LocalStartRun | SshStartRun;
export interface RemoteRunControls {
  runs: DesktopAPI["runs"];
  authority?: { expectedRevision: number; expectedProgramHash: string };
  onBinding(binding: RemoteBinding | null): void;
  onSession(session: AuthenticatedConnection | null): void;
}
export type ConnectionState = "connected" | "reconnecting" | "closed" | "error";
export interface DesktopAPI {
  dataTransfers?: {
    history?(projectId: string): Promise<TransferHistory[]>;
    inspect?(
      slotId: string,
      request: TransferPlanRequest,
    ): Promise<TransferPlan>;
    plan(request: TransferPlanRequest): Promise<TransferPlan>;
    confirm(request: TransferConfirmation): Promise<TransferJob>;
    get(
      id: string,
      scope: { projectId: string; connectionId: string },
    ): Promise<TransferJob>;
    cancel(
      id: string,
      scope: { projectId: string; connectionId: string },
    ): Promise<TransferJob>;
  };
  packages?: {
    history(): Promise<InstallJobHistory>;
    report(jobId: string): Promise<InstallJobReport>;
    chooseSources(
      request: InstallSourceSelection,
    ): Promise<InstallSourcePreview | null>;
    confirmSources(
      request: InstallSourceConfirmation,
    ): Promise<InstallSourceResult>;
    catalog(): Promise<PackageCatalog>;
    plan(request: InstallPlanRequest): Promise<InstallPlan>;
    confirm(request: InstallConfirmation): Promise<InstallJob>;
    job(jobId: string): Promise<InstallJob>;
    cancel(jobId: string): Promise<InstallJob>;
  };
  connections: {
    listProfiles(): Promise<ConnectionProfile[]>;
    createProfile(request: ConnectionProfileInput): Promise<ConnectionProfile>;
    updateProfile(
      targetId: string,
      request: ConnectionProfileUpdate,
    ): Promise<ConnectionProfile>;

    authenticate(
      projectId: string,
      requestId: string,
      identityRequestId: string,
      username: string,
      password: string,
      target?: ConnectionTargetReference,
    ): Promise<AuthenticatedConnection>;
    authenticateKey?(
      projectId: string,
      requestId: string,
      identityRequestId: string,
      username: string,
      passphrase: string,
      target?: ConnectionTargetReference,
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
  local: {
    preflight(request: LocalPreflightRequest): Promise<LocalPreflightResult>;
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
    exportBundle?(
      projectId: string,
      expectedRevision: number,
      expectedProgramHash: string,
    ): Promise<BundleExportResult | null>;
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
    bind(request: RemoteBindingRequest): Promise<RemoteBinding>;
    resume(
      runId: string,
      projectId: string,
      connectionId: string,
    ): Promise<Run>;
    list(projectId: string, offset: number, limit: number): Promise<Run[]>;
    start(request: StartRun): Promise<Run>;
    get(runId: string): Promise<Run>;
    cancel(runId: string): Promise<Run>;
    source(runId: string): Promise<RunSource>;
    report?(runId: string, eventSeq: number): Promise<DiagnosticReport>;
    exportDiagnostic?(
      runId: string,
      eventSeq: number,
    ): Promise<{ exported: boolean }>;
    logs(
      runId: string,
      stdoutAfter: number,
      stderrAfter: number,
    ): Promise<RunLogs>;
    pauseArtifactSync?(runId: string): Promise<Run>;
    resumeArtifactSync?(runId: string): Promise<Run>;
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
