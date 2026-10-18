/* Generated from Pydantic. Do not edit. */

export type Exported = true;
export type Projectid = string;
export type Projectrevision = number;
export type Programhash = string;
export type Codehash = string;
export type Bundlehash = string;
export type Directoryname = string;

export interface BundleExportResult {
  exported?: Exported;
  projectId: Projectid;
  projectRevision: Projectrevision;
  programHash: Programhash;
  codeHash: Codehash;
  bundleHash: Bundlehash;
  directoryName: Directoryname;
}
