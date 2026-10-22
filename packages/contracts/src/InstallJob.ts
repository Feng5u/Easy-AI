/* Generated from Pydantic. Do not edit. */

export type Targetid = "local" | string;
export type Projectid = string;
export type Targetid1 = string;
export type Targetrevision = number;
export type Host = string;
export type Port = number;
export type Hostfingerprint = string;
export type Username = string;
export type Root = string;
/**
 * @maxItems 17
 */
export type Selectedpackages =
  | []
  | [string]
  | [string, string]
  | [string, string, string]
  | [string, string, string, string]
  | [string, string, string, string, string]
  | [string, string, string, string, string, string]
  | [string, string, string, string, string, string, string]
  | [string, string, string, string, string, string, string, string]
  | [string, string, string, string, string, string, string, string, string]
  | [string, string, string, string, string, string, string, string, string, string]
  | [string, string, string, string, string, string, string, string, string, string, string]
  | [string, string, string, string, string, string, string, string, string, string, string, string]
  | [string, string, string, string, string, string, string, string, string, string, string, string, string]
  | [string, string, string, string, string, string, string, string, string, string, string, string, string, string]
  | [
      string,
      string,
      string,
      string,
      string,
      string,
      string,
      string,
      string,
      string,
      string,
      string,
      string,
      string,
      string
    ]
  | [
      string,
      string,
      string,
      string,
      string,
      string,
      string,
      string,
      string,
      string,
      string,
      string,
      string,
      string,
      string,
      string
    ]
  | [
      string,
      string,
      string,
      string,
      string,
      string,
      string,
      string,
      string,
      string,
      string,
      string,
      string,
      string,
      string,
      string,
      string
    ];
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
  targetId?: Targetid;
  targetIdentity?: InstallTargetIdentity | null;
  selectedPackages?: Selectedpackages;
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
export interface InstallTargetIdentity {
  projectId: Projectid;
  targetId: Targetid1;
  targetRevision: Targetrevision;
  endpoint: SshEndpoint;
  hostFingerprint: Hostfingerprint;
  username: Username;
  root: Root;
}
export interface SshEndpoint {
  host: Host;
  port?: Port;
}
