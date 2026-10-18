/* Generated from Pydantic. Do not edit. */

export type Protocolversion = 1;
export type Projectid = string;
export type Targetid = string;
export type Runid = string;
export type Launchid = string;
export type Username = string;
export type Host = string;
export type Port = number;
export type Hostfingerprint = string;
export type Runroot = string;
export type Programhash = string;
export type Codehash = string;
export type Bundlehash = string;
export type Confighash = string;
export type Startoutcome = "not_attempted" | "unknown" | "acknowledged";
export type Cancelstate = "none" | "pending" | "acknowledged" | "resolved";
export type Executionstate =
  | "CREATED"
  | "STAGING"
  | "STARTING"
  | "RUNNING"
  | "CANCELLING"
  | "CLEANUP_PENDING"
  | "COMPLETED"
  | "FAILED"
  | "CANCELLED";
export type Connectionstate = "connected" | "disconnected";
export type Artifactsverified = false;
export type Lastconnectionid = string | null;
export type Heartbeat = number;
export type State = "STARTING" | "RUNNING" | "CANCELLING" | "CLEANUP_PENDING" | "COMPLETED" | "FAILED" | "CANCELLED";
export type Sealed = boolean;
export type Exitcode = number | null;
export type Generation = string;
export type Sizebytes = number;
export type Sha256 = string;

export interface RemoteRunCheckpoint {
  protocolVersion?: Protocolversion;
  identity: RemoteRunIdentity;
  startOutcome?: Startoutcome;
  cancelState?: Cancelstate;
  executionState?: Executionstate;
  connectionState?: Connectionstate;
  artifactsVerified?: Artifactsverified;
  lastConnectionId?: Lastconnectionid;
  lastObservation?: RemoteRunObservation | null;
}
export interface RemoteRunIdentity {
  projectId: Projectid;
  targetId: Targetid;
  runId: Runid;
  launchId: Launchid;
  username: Username;
  endpoint: SshEndpoint;
  hostFingerprint: Hostfingerprint;
  runRoot: Runroot;
  programHash: Programhash;
  codeHash: Codehash;
  bundleHash: Bundlehash;
  configHash: Confighash;
}
export interface SshEndpoint {
  host: Host;
  port?: Port;
}
export interface RemoteRunObservation {
  identity: RemoteRunIdentity;
  heartbeat: Heartbeat;
  state: State;
  sealed: Sealed;
  exitCode?: Exitcode;
  streams: RemoteStreams;
}
export interface RemoteStreams {
  events: RemoteStream;
  stdout: RemoteStream;
  stderr: RemoteStream;
}
export interface RemoteStream {
  generation: Generation;
  sizeBytes: Sizebytes;
  sha256: Sha256;
}
