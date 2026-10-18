/* Generated from Pydantic. Do not edit. */

export type Targetid = string | null;
export type Targetrevision = number | null;
export type Projectid = string;
export type Requestid = string;
export type Identityrequestid = string;
export type Expectedfingerprint = string;
export type Username = string;

export interface AuthenticationRequest {
  targetId?: Targetid;
  targetRevision?: Targetrevision;
  projectId: Projectid;
  requestId: Requestid;
  identityRequestId: Identityrequestid;
  expectedFingerprint: Expectedfingerprint;
  username: Username;
}
