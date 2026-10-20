/* Generated from Pydantic. Do not edit. */

export type Previewid = string;
export type Previewhash = string;
export type Packageids = string[];
export type Sourcename = string;
export type Manifestsha256 = string;
export type Name = string;
export type Sha256 = string;
export type Bytes = number;
export type Modulename = string;
export type Moduletreesha256 = string;
export type Bootstrap = InstallSourceArtifact[];
export type Wheels = InstallSourceArtifact[];
export type Sourcebytes = number;
export type Installedbytes = null;
export type Diskbudgetbytes = number;
export type Executionseconds = number;
export type Authorizationexpires = string;
export type Declaredexecutionauthorized = boolean;
export type Executionenabled = false;
export type Expiresat = string;

export interface InstallSourcePreview {
  previewId: Previewid;
  previewHash: Previewhash;
  packageIds: Packageids;
  sourceName: Sourcename;
  manifestSha256: Manifestsha256;
  launcher: InstallSourceArtifact;
  moduleName: Modulename;
  moduleTreeSha256: Moduletreesha256;
  bootstrap: Bootstrap;
  wheels: Wheels;
  sourceBytes: Sourcebytes;
  installedBytes?: Installedbytes;
  diskBudgetBytes: Diskbudgetbytes;
  executionSeconds: Executionseconds;
  authorizationExpires: Authorizationexpires;
  declaredExecutionAuthorized: Declaredexecutionauthorized;
  executionEnabled?: Executionenabled;
  expiresAt: Expiresat;
}
export interface InstallSourceArtifact {
  name: Name;
  sha256: Sha256;
  bytes: Bytes;
}
