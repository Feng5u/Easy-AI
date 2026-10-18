/* Generated from Pydantic. Do not edit. */

export type Runner = "ssh";
export type Bindingid = string;
export type Expectedrevision = number;
export type Expectedprogramhash = string;

export interface RemoteRunStartRequest {
  runner: Runner;
  bindingId: Bindingid;
  expectedRevision: Expectedrevision;
  expectedProgramHash: Expectedprogramhash;
}
