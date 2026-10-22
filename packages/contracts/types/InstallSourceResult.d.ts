/* Generated from Pydantic. Do not edit. */

export type Previewid = string;
export type Manifestsha256 = string;
export type Runtimefingerprint = string;
export type Executionenabled = false;
export type Authorizationexpires = string;

export interface InstallSourceResult {
  previewId: Previewid;
  manifestSha256: Manifestsha256;
  runtimeFingerprint: Runtimefingerprint;
  executionEnabled?: Executionenabled;
  authorizationExpires: Authorizationexpires;
}
