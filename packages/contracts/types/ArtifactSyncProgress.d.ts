/* Generated from Pydantic. Do not edit. */

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
