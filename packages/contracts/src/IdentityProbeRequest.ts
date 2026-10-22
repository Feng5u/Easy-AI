/* Generated from Pydantic. Do not edit. */

export type Projectid = string;
export type Requestid = string;
export type Host = string;
export type Port = number;

export interface IdentityProbeRequest {
  projectId: Projectid;
  requestId: Requestid;
  endpoint: SshEndpoint;
}
export interface SshEndpoint {
  host: Host;
  port?: Port;
}
