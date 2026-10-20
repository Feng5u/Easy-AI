/* Generated from Pydantic. Do not edit. */

export type Projectid = string;
export type Connectionid = string;
export type Host = string;
export type Port = number;
export type Hostfingerprint = string;

export interface EnvironmentScope {
  projectId: Projectid;
  connectionId: Connectionid;
  endpoint: SshEndpoint;
  hostFingerprint: Hostfingerprint;
}
export interface SshEndpoint {
  host: Host;
  port?: Port;
}
