/* Generated from Pydantic. Do not edit. */

export type Projectid = string;
export type Connectionid = string;
export type Requestid = string;

export interface EnvironmentRequest {
  projectId: Projectid;
  connectionId: Connectionid;
  requestId: Requestid;
}
