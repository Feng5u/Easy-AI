/* Generated from Pydantic. Do not edit. */

export type Projectid = string;
export type Requestid = string;
export type Challengeid = string;
export type Fingerprint = string;

export interface IdentityConfirmRequest {
  projectId: Projectid;
  requestId: Requestid;
  confirmation: HostKeyConfirmation;
}
export interface HostKeyConfirmation {
  challengeId: Challengeid;
  fingerprint: Fingerprint;
}
