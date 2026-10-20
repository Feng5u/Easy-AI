/* Generated from Pydantic. Do not edit. */

export type Host = string;
export type Port = number;

export interface SshEndpoint {
  host: Host;
  port?: Port;
}
