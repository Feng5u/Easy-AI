/* Generated from Pydantic. Do not edit. */

export type Transferid = string;
export type Projectid = string;
export type Targetid = string;
export type Targetrevision = number;
export type Targetpath = string;
export type Filecount = number;
export type Totalbytes = number;
export type Lastcompleted = boolean;
export type Inspectionrequired = true;

export interface TransferHistory {
  transferId: Transferid;
  projectId: Projectid;
  targetId: Targetid;
  targetRevision: Targetrevision;
  targetPath: Targetpath;
  fileCount: Filecount;
  totalBytes: Totalbytes;
  lastCompleted: Lastcompleted;
  inspectionRequired?: Inspectionrequired;
}
