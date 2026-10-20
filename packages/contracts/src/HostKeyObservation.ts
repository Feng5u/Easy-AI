/* Generated from Pydantic. Do not edit. */

export type Host = string;
export type Port = number;
export type Algorithm = string;
export type Fingerprint = string;
export type Truststate = "trusted" | "unknown" | "changed";
export type Challengeid = string | null;
export type Previousfingerprint = string | null;

export interface HostKeyObservation {
  endpoint: SshEndpoint;
  algorithm: Algorithm;
  fingerprint: Fingerprint;
  trustState: Truststate;
  challengeId?: Challengeid;
  previousFingerprint?: Previousfingerprint;
}
export interface SshEndpoint {
  host: Host;
  port?: Port;
}
