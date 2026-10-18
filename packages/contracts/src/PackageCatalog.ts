/* Generated from Pydantic. Do not edit. */

export type Catalogversion = 1;
export type Packageid = string;
export type Importname = string;
export type Group = "ml" | "dl" | "cv" | "nlp";
export type Purpose = string;
export type Dependencynote = string;
export type Installedstatus = "unknown";
export type Installedversion = string | null;
export type Targetversion = string | null;
export type Packages = PackageCard[];
export type Profiles = ("teacher-existing" | "easyai-cpu")[];
export type Executionenabled = boolean;

export interface PackageCatalog {
  catalogVersion?: Catalogversion;
  packages: Packages;
  profiles: Profiles;
  executionEnabled?: Executionenabled;
}
export interface PackageCard {
  packageId: Packageid;
  importName: Importname;
  group: Group;
  purpose: Purpose;
  dependencyNote: Dependencynote;
  installedStatus?: Installedstatus;
  installedVersion?: Installedversion;
  targetVersion: Targetversion;
}
