/* Generated from Pydantic. Do not edit. */

export type Planid = string;
export type Planhash = string;
export type Targetid = "local";
export type Profileid = "easyai-cpu";
export type Environmentid = string;
export type Environmentname = string;
export type Newenvironment = boolean;
export type Baselinefingerprint = string;
export type Constraintshash = string;
export type Packageid = string;
export type Previousversion = string | null;
export type Targetversion = string | null;
export type Action = "add" | "keep" | "unresolved";
export type Requested = boolean;
export type Packagechanges = PackageChange[];
export type Requiresnetwork = true;
export type Downloadbytes = number | null;
export type Installedbytes = number | null;
export type Sizestatus = "locked-wheel-estimate" | "unresolved";
export type Platform = string;
export type Blockers = string[];
export type Executionenabled = false;

export interface InstallPlan {
  planId: Planid;
  planHash: Planhash;
  targetId?: Targetid;
  profileId?: Profileid;
  environmentId: Environmentid;
  environmentName: Environmentname;
  newEnvironment: Newenvironment;
  baselineFingerprint: Baselinefingerprint;
  constraintsHash: Constraintshash;
  packageChanges: Packagechanges;
  requiresNetwork?: Requiresnetwork;
  downloadBytes: Downloadbytes;
  installedBytes: Installedbytes;
  sizeStatus: Sizestatus;
  platform: Platform;
  blockers: Blockers;
  executionEnabled?: Executionenabled;
}
export interface PackageChange {
  packageId: Packageid;
  previousVersion: Previousversion;
  targetVersion: Targetversion;
  action: Action;
  requested: Requested;
}
