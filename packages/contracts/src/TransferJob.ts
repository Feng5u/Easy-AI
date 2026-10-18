/* Generated from Pydantic. Do not edit. */

export type Transferid = string;
export type Planid = string;
export type Planhash = string;
export type Projectid = string;
export type Connectionid = string;
export type Targetpath = string;
export type Status =
  "UPLOADING" | "VERIFYING" | "CANCELLING" | "CLEANUP_PENDING" | "COMPLETED" | "CANCELLED" | "FAILED";
export type Filecount = number;
export type Totalbytes = number;
export type Reusedbytes = number;
export type Sentbytes = number;
export type Verifiedbytes = number;
export type Completedfiles = number;
export type Errorcode =
  | (
      | "DATA_TRANSFER_AUTH_STALE"
      | "DATA_TRANSFER_BUSY"
      | "DATA_TRANSFER_CANCELLED"
      | "DATA_TRANSFER_CLEANUP_PENDING"
      | "DATA_TRANSFER_CLEANUP_FAILED"
      | "DATA_TRANSFER_CLOSED"
      | "DATA_TRANSFER_CONFIRMATION_INVALID"
      | "DATA_TRANSFER_CONFIRMATION_REQUIRED"
      | "DATA_TRANSFER_FAILED"
      | "DATA_TRANSFER_RECOVERY_INVALID"
      | "DATA_TRANSFER_PERSISTENCE_FAILED"
      | "DATA_TRANSFER_HASH_MISMATCH"
      | "DATA_TRANSFER_HOME_CHANGED"
      | "DATA_TRANSFER_HOME_INVALID"
      | "DATA_TRANSFER_JOB_LIMIT"
      | "DATA_TRANSFER_MANIFEST_LIMIT"
      | "DATA_TRANSFER_NOT_FOUND"
      | "DATA_TRANSFER_PLAN_EXPIRED"
      | "DATA_TRANSFER_PROGRESS_INVALID"
      | "DATA_TRANSFER_SOURCE_CHANGED"
      | "DATA_TRANSFER_SOURCE_EMPTY"
      | "DATA_TRANSFER_SOURCE_FORBIDDEN"
      | "DATA_TRANSFER_SOURCE_LIMIT"
      | "DATA_TRANSFER_START_FAILED"
      | "DATA_TRANSFER_TARGET_REQUIRED"
      | "DATA_TRANSFER_TARGET_UNOWNED"
      | "DATA_TRANSFER_TIMEOUT"
      | "DATA_TRANSFER_VERIFICATION_INCOMPLETE"
    )
  | null;
export type Dataready = false;

export interface TransferJob {
  transferId: Transferid;
  planId: Planid;
  planHash: Planhash;
  projectId: Projectid;
  connectionId: Connectionid;
  targetPath: Targetpath;
  status: Status;
  fileCount: Filecount;
  totalBytes: Totalbytes;
  reusedBytes?: Reusedbytes;
  sentBytes?: Sentbytes;
  verifiedBytes?: Verifiedbytes;
  completedFiles?: Completedfiles;
  errorCode?: Errorcode;
  dataReady?: Dataready;
}
