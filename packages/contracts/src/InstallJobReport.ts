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
export type Jobid1 = string;
export type Planid1 = string;
export type Planhash1 = string;
export type Environmentid1 = string;
export type State1 =
  "AWAITING_EXECUTION" | "INSTALLING" | "VERIFYING" | "SUCCEEDED" | "FAILED" | "CANCEL_REQUESTED" | "CANCELLED";
export type Statuscode1 = string;
/**
 * @maxItems 128
 */
export type Logs = string[];
export type Needsreprobe = boolean;
export type Changespossible = boolean;
export type Verified = boolean;
export type Executionenabled = boolean;
export type Currentenvironmentverified = false;

export interface InstallJobReport {
  summary: InstallJobSummary;
  recorded: InstallJob;
  observed: InstallJob;
  currentEnvironmentVerified?: Currentenvironmentverified;
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
export interface InstallJob {
  jobId: Jobid1;
  planId: Planid1;
  planHash: Planhash1;
  environmentId: Environmentid1;
  state: State1;
  statusCode: Statuscode1;
  logs: Logs;
  needsReprobe?: Needsreprobe;
  changesPossible?: Changespossible;
  verified?: Verified;
  executionEnabled?: Executionenabled;
}
