/* Generated from Pydantic. Do not edit. */

export type Maxfiles = number;
export type Maxbytes = number;
export type Seconds = number;

export interface TransferBudget {
  maxFiles?: Maxfiles;
  maxBytes?: Maxbytes;
  seconds?: Seconds;
}
