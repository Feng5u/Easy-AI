/* Generated from Pydantic. Do not edit. */

export type Projectid = string;
export type Connectionid = string;
export type Expectedrevision = number;
export type Dataselectionid = string;
export type Maxfiles = number;
export type Maxbytes = number;
export type Seconds = number;

export interface TransferPlanRequest {
  projectId: Projectid;
  connectionId: Connectionid;
  expectedRevision: Expectedrevision;
  dataSelectionId: Dataselectionid;
  budget: TransferBudget;
}
export interface TransferBudget {
  maxFiles?: Maxfiles;
  maxBytes?: Maxbytes;
  seconds?: Seconds;
}
