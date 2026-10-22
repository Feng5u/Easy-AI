/* Generated from Pydantic. Do not edit. */

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
export type Heartbeat = number;
export type Sha256 = string;
export type Sourceseq = number;
export type Eventssha256 = string;
export type State = "STARTING" | "RUNNING" | "CANCELLING" | "CLEANUP_PENDING" | "COMPLETED" | "FAILED" | "CANCELLED";
export type Sealed = boolean;
export type Spawnfailed = boolean;
export type Exitcode = number | null;
export type Generation = string;
export type Sizebytes = number;
export type Sha2561 = string;

export interface RemoteRunObservation {
  identity: RemoteRunIdentity;
  heartbeat: Heartbeat;
  artifactReceipt?: ArtifactReceipt | null;
  state: State;
  sealed: Sealed;
  spawnFailed?: Spawnfailed;
  exitCode?: Exitcode;
  streams: RemoteStreams;
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
/**
 * Immutable manifest and exact raw-event prefix, published before owner status.
 */
export interface ArtifactReceipt {
  sha256: Sha256;
  sourceSeq: Sourceseq;
  eventsSha256: Eventssha256;
}
export interface RemoteStreams {
  events: RemoteStream;
  stdout: RemoteStream;
  stderr: RemoteStream;
}
export interface RemoteStream {
  generation: Generation;
  sizeBytes: Sizebytes;
  sha256: Sha2561;
}
