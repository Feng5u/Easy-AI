/* Generated from Pydantic. Do not edit. */

export type Jobid = string;
export type Environmentid = string;
export type Planid = string;
export type Planhash = string;
export type Recordedat = string;
export type Recordedstate =
  "AWAITING_EXECUTION" | "INSTALLING" | "VERIFYING" | "SUCCEEDED" | "FAILED" | "CANCEL_REQUESTED" | "CANCELLED";
export type State =
  "AWAITING_EXECUTION" | "INSTALLING" | "VERIFYING" | "SUCCEEDED" | "FAILED" | "CANCEL_REQUESTED" | "CANCELLED";
export type Statuscode = string;
export type Origin = "current" | "recovered" | "external";
export type Workeralive = boolean;
export type Observation = "managed-worker-alive" | "registered-only" | "historical" | "stop-unconfirmed";
/**
 * @maxItems 64
 */
export type Entries = InstallJobSummary[];
export type Limit = 64;

export interface InstallJobHistory {
  entries: Entries;
  limit?: Limit;
}
export interface InstallJobSummary {
  jobId: Jobid;
  environmentId: Environmentid;
  planId: Planid;
  planHash: Planhash;
  recordedAt: Recordedat;
  recordedState: Recordedstate;
  state: State;
  statusCode: Statuscode;
  origin: Origin;
  workerAlive: Workeralive;
  observation: Observation;
}
