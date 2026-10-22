/* Generated from Pydantic. Do not edit. */

export type Planid = string;
export type Planhash = string;
export type Confirmed = true;
export type Networkacknowledged = true;

export interface InstallConfirmation {
  planId: Planid;
  planHash: Planhash;
  confirmed: Confirmed;
  networkAcknowledged: Networkacknowledged;
}
