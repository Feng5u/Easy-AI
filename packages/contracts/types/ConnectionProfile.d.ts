/* Generated from Pydantic. Do not edit. */

export type Alias = string;
export type Host = string;
export type Port = number;
export type Username = string;
export type Targetid = string;
export type Revision = number;

export interface ConnectionProfile {
  alias: Alias;
  endpoint: SshEndpoint;
  username: Username;
  targetId: Targetid;
  revision: Revision;
}
export interface SshEndpoint {
  host: Host;
  port?: Port;
}
