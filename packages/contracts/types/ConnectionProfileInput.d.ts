/* Generated from Pydantic. Do not edit. */

export type Alias = string;
export type Host = string;
export type Port = number;
export type Username = string;

export interface ConnectionProfileInput {
  alias: Alias;
  endpoint: SshEndpoint;
  username: Username;
}
export interface SshEndpoint {
  host: Host;
  port?: Port;
}
