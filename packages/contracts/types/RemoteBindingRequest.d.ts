/* Generated from Pydantic. Do not edit. */

export type Projectid = string;
export type Connectionid = string;
export type Requestid = string;
export type Expectedrevision = number;
export type Expectedprogramhash = string;
export type Proberequestid = string;
export type Runbase = string;

export interface RemoteBindingRequest {
  projectId: Projectid;
  connectionId: Connectionid;
  requestId: Requestid;
  expectedRevision: Expectedrevision;
  expectedProgramHash: Expectedprogramhash;
  probeRequestId: Proberequestid;
  runBase: Runbase;
}
