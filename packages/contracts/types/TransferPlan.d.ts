/* Generated from Pydantic. Do not edit. */

export type Planid = string;
export type Planhash = string;
export type Projectid = string;
export type Connectionid = string;
export type Targetid = string;
export type Targetrevision = number;
export type Sourcelabel = string;
export type Targetpath = string;
export type Filecount = number;
export type Totalbytes = number;
export type Maxfiles = number;
export type Maxbytes = number;
export type Seconds = number;
export type Expiresinseconds = number;
export type Writesstarted = false;
export type Slotid = string | null;
export type Reusedbytes = number;
export type Missingfiles = number;

export interface TransferPlan {
  planId: Planid;
  planHash: Planhash;
  projectId: Projectid;
  connectionId: Connectionid;
  targetId: Targetid;
  targetRevision: Targetrevision;
  sourceLabel: Sourcelabel;
  targetPath: Targetpath;
  fileCount: Filecount;
  totalBytes: Totalbytes;
  budget: TransferBudget;
  expiresInSeconds: Expiresinseconds;
  writesStarted?: Writesstarted;
  slotId?: Slotid;
  reusedBytes?: Reusedbytes;
  missingFiles?: Missingfiles;
}
export interface TransferBudget {
  maxFiles?: Maxfiles;
  maxBytes?: Maxbytes;
  seconds?: Seconds;
}
