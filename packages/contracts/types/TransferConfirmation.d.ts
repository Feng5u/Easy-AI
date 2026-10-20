/* Generated from Pydantic. Do not edit. */

export type Projectid = string;
export type Connectionid = string;
export type Planid = string;
export type Planhash = string;
export type Confirmed = true;

export interface TransferConfirmation {
  projectId: Projectid;
  connectionId: Connectionid;
  planId: Planid;
  planHash: Planhash;
  confirmed: Confirmed;
}
