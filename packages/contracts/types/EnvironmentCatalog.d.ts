/* Generated from Pydantic. Do not edit. */

export type Projectid = string;
export type Connectionid = string;
export type Requestid = string;
export type Projectid1 = string;
export type Connectionid1 = string;
export type Host = string;
export type Port = number;
export type Hostfingerprint = string;
export type Environmentid = string;
export type Kind = "conda" | "python";
export type Location = string;
export type Readonly = true;
/**
 * @maxItems 64
 */
export type Environments = EnvironmentDescriptor[];
export type Condaexecutable = string | null;
export type Condaversion = string | null;
export type Note = "unprobed" | "conda_not_found";

export interface EnvironmentCatalog {
  projectId: Projectid;
  connectionId: Connectionid;
  requestId: Requestid;
  scope: EnvironmentScope;
  environments: Environments;
  condaExecutable?: Condaexecutable;
  condaVersion?: Condaversion;
  note?: Note;
}
export interface EnvironmentScope {
  projectId: Projectid1;
  connectionId: Connectionid1;
  endpoint: SshEndpoint;
  hostFingerprint: Hostfingerprint;
}
export interface SshEndpoint {
  host: Host;
  port?: Port;
}
export interface EnvironmentDescriptor {
  environmentId: Environmentid;
  kind: Kind;
  location: Location;
  readOnly?: Readonly;
}
