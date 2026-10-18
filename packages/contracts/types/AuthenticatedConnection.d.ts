/* Generated from Pydantic. Do not edit. */

export type Projectid = string;
export type Requestid = string;
export type Identityrequestid = string;
export type Projectid1 = string;
export type Connectionid = string;
export type Host = string;
export type Port = number;
export type Hostfingerprint = string;
export type Username = string;
export type Authenticated = true;
export type Method = "password";
export type Expiresinseconds = number;

export interface AuthenticatedConnection {
  projectId: Projectid;
  requestId: Requestid;
  identityRequestId: Identityrequestid;
  scope: EnvironmentScope;
  username: Username;
  authenticated?: Authenticated;
  method?: Method;
  expiresInSeconds: Expiresinseconds;
}
export interface EnvironmentScope {
  projectId: Projectid1;
  connectionId: Connectionid;
  endpoint: SshEndpoint;
  hostFingerprint: Hostfingerprint;
}
export interface SshEndpoint {
  host: Host;
  port?: Port;
}
