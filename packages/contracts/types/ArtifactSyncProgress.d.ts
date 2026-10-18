/* Generated from Pydantic. Do not edit. */

export type State = "idle" | "syncing" | "paused" | "cleanup_pending" | "error";
export type Receivedbytes = number;
export type Verifiedbytes = number;
export type Totalbytes = number;

export interface ArtifactSyncProgress {
  state?: State;
  receivedBytes?: Receivedbytes;
  verifiedBytes?: Verifiedbytes;
  totalBytes?: Totalbytes;
}
