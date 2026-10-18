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
  status: { get(): Promise<{ ready: boolean; message: string }> };
  selections: { pick(kind: SelectionKind): Promise<SelectionResult | null> };
  projects: {
    current(): Promise<ProjectSession | null>;
    open(selectionId: string): Promise<ProjectSession>;
    create(selectionId: string, name: string): Promise<ProjectSession>;
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
