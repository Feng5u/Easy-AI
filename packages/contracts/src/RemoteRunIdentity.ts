/* Generated from Pydantic. Do not edit. */

export type Projectid = string;
export type Targetid = string;
export type Runid = string;
export type Launchid = string;
export type Username = string;
export type Host = string;
export type Port = number;
export type Hostfingerprint = string;
export type Runroot = string;
export type Programhash = string;
export type Codehash = string;
export type Bundlehash = string;
export type Confighash = string;

export interface RemoteRunIdentity {
  projectId: Projectid;
  targetId: Targetid;
  runId: Runid;
  launchId: Launchid;
  username: Username;
  endpoint: SshEndpoint;
  hostFingerprint: Hostfingerprint;
  runRoot: Runroot;
  programHash: Programhash;
  codeHash: Codehash;
  bundleHash: Bundlehash;
  configHash: Confighash;
}
export interface SshEndpoint {
  host: Host;
  port?: Port;
}
