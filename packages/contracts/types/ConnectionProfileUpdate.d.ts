/* Generated from Pydantic. Do not edit. */

export type Alias = string;
export type Host = string;
export type Port = number;
export type Username = string;
export type Expectedrevision = number;

export interface ConnectionProfileUpdate {
  alias: Alias;
  endpoint: SshEndpoint;
  username: Username;
  expectedRevision: Expectedrevision;
}
export interface SshEndpoint {
  host: Host;
  port?: Port;
}
