/* Generated from Pydantic. Do not edit. */

export type Jobid = string;
export type Planid = string;
export type Planhash = string;
export type Environmentid = string;
export type State =
  "AWAITING_EXECUTION" | "INSTALLING" | "VERIFYING" | "SUCCEEDED" | "FAILED" | "CANCEL_REQUESTED" | "CANCELLED";
export type Statuscode = string;
/**
 * @maxItems 128
 */
export type Logs = string[];
export type Needsreprobe = boolean;
export type Changespossible = boolean;
export type Verified = boolean;
export type Executionenabled = boolean;

export interface InstallJob {
  jobId: Jobid;
  planId: Planid;
  planHash: Planhash;
  environmentId: Environmentid;
  state: State;
  statusCode: Statuscode;
  logs: Logs;
  needsReprobe?: Needsreprobe;
  changesPossible?: Changespossible;
  verified?: Verified;
  executionEnabled?: Executionenabled;
}
