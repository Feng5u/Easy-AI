/* Generated from Pydantic. Do not edit. */

export type Runid = string;
export type Projectid = string;
export type Status =
  | "CREATED"
  | "PRECHECKING"
  | "STAGING"
  | "STARTING"
  | "RUNNING"
  | "CLEANUP_PENDING"
  | "COMPLETED"
  | "SUCCEEDED"
  | "FAILED"
  | "CANCELLING"
  | "CANCELLED"
  | "INTERRUPTED";
export type Connectionstate = "connected" | "disconnected" | "reconnecting";
export type Syncstate = "pending" | "syncing" | "complete" | "error";
export type Configversion = 1;
export type Runid1 = string;
export type Projectid1 = string;
export type Projectrevision = number;
export type Programhash = string;
export type Codehash = string;
export type Bundlehash = string;
export type Targetid = string;
export type Runner = "local" | "ssh";
export type Dataroot = string;
export type Runroot = string;
export type Pythonexecutable = string;
export type Environmentprefix = string | null;
export type Condaexecutable = string | null;
export type Device = "auto" | "cpu" | "cuda" | "mps";
export type Executionmode = "full" | "quick";
export type Seed = number;
export type Numworkers = number;
export type Pinmemorypolicy = "cuda_only";
export type Epochs = 1;
export type Trainsamples = 1024;
export type Testsamples = 256;
export type Host = string;
export type Port = number;
export type Username = string;
export type Hostfingerprint = string;
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
export type Startoutcome = "not_attempted" | "unknown" | "acknowledged";
export type Cancelstate = "none" | "pending" | "acknowledged" | "resolved";
export type Artifactsverified = boolean;
export type State = "idle" | "syncing" | "paused" | "cleanup_pending" | "error";
export type Receivedbytes = number;
export type Verifiedbytes = number;
export type Totalbytes = number;
export type Stage =
  | "scope"
  | "owner_poll"
  | "snapshot"
  | "event_prefix"
  | "receipt_read"
  | "receipt_digest"
  | "receipt_records"
  | "cache_open"
  | "artifact_read"
  | "artifact_verify"
  | "cache_commit"
  | "channel_cleanup"
  | "cache_cleanup"
  | "watcher_cleanup"
  | "completion"
  | "unknown";
export type Code =
  | "SYNC_INVALID_EVIDENCE"
  | "SYNC_IO_FAILED"
  | "SYNC_CANCELLED"
  | "SYNC_DEADLINE"
  | "SYNC_AUTH_STALE"
  | "SYNC_BUSY"
  | "SYNC_CLEANUP_UNCONFIRMED"
  | "SYNC_REQUIRED_ARTIFACTS_MISSING"
  | "SYNC_UNKNOWN";

export interface Run {
  runId: Runid;
  projectId: Projectid;
  status: Status;
  connectionState: Connectionstate;
  syncState: Syncstate;
  config: RunConfig;
  remote?: RemoteExecution | null;
  artifactSync?: ArtifactSyncProgress | null;
}
export interface RunConfig {
  configVersion?: Configversion;
  runId: Runid1;
  projectId: Projectid1;
  projectRevision: Projectrevision;
  programHash: Programhash;
  codeHash: Codehash;
  bundleHash: Bundlehash;
  targetId: Targetid;
  runner: Runner;
  dataRoot: Dataroot;
  runRoot: Runroot;
  pythonExecutable: Pythonexecutable;
  environmentPrefix?: Environmentprefix;
  condaExecutable?: Condaexecutable;
  device?: Device;
  executionMode: Executionmode;
  seed: Seed;
  numWorkers: Numworkers;
  pinMemoryPolicy?: Pinmemorypolicy;
  quickLimits?: QuickLimits | null;
}
export interface QuickLimits {
  epochs?: Epochs;
  trainSamples?: Trainsamples;
  testSamples?: Testsamples;
}
export interface RemoteExecution {
  host: Host;
  port: Port;
  username: Username;
  hostFingerprint: Hostfingerprint;
  executionState: Executionstate;
  startOutcome: Startoutcome;
  cancelState: Cancelstate;
  artifactsVerified?: Artifactsverified;
}
export interface ArtifactSyncProgress {
  state?: State;
  receivedBytes?: Receivedbytes;
  verifiedBytes?: Verifiedbytes;
  totalBytes?: Totalbytes;
  failure?: ArtifactSyncFailure | null;
  cleanupFailure?: ArtifactSyncFailure | null;
}
export interface ArtifactSyncFailure {
  stage: Stage;
  code: Code;
}
