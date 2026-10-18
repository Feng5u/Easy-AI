/* Generated from Pydantic. Do not edit. */

export type Projectrevision = number;
export type Programhash = string;
export type Codehash = string;
export type Code = string;
export type File = "train.py";
export type Startline = number;
export type Endline = number;
export type Blockid = string;
export type Workspace = "data" | "model" | "training";
export type Kind = "semantic" | "scaffold";
export type Sourcemap = SourceSpan[];
export type Schemaversion = 1;
export type Appversion = "0.0.0";
export type Blocklibraryversion = "0.0.0";
export type Projectid = string;
export type Name = string;
export type Revision = number;
export type Languageversion = 0;
export type Blocks = {
  [k: string]: unknown;
}[];
export type Datadirectory = "data";
export type Seed = number;
export type Executionmode = "full" | "quick";
export type Activetab = "data" | "model" | "training";
export type Codevisible = boolean;
export type Blockid1 = string;
export type Kind1 = "transform" | "dataset" | "dataloader" | "model_class";
export type Role = ("train" | "test") | null;
export type Workspace2 = "data" | "model";
export type Registered = boolean;
export type Objects = SnapshotObject[];
export type Referencecheck = "passed" | "failed" | "unavailable";

export interface RunSource {
  projectRevision: Projectrevision;
  programHash: Programhash;
  codeHash: Codehash;
  code: Code;
  sourceMap: Sourcemap;
  snapshot: ProjectDocument;
  objects?: Objects;
  referenceCheck?: Referencecheck;
}
export interface SourceSpan {
  file?: File;
  startLine: Startline;
  endLine: Endline;
  origin: Origin;
  kind: Kind;
}
export interface Origin {
  blockId: Blockid;
  workspace: Workspace;
}
export interface ProjectDocument {
  schemaVersion?: Schemaversion;
  appVersion?: Appversion;
  blockLibraryVersion?: Blocklibraryversion;
  projectId: Projectid;
  name: Name;
  revision: Revision;
  workspaces: Workspaces;
  settings?: Settings;
  ui?: UI;
}
export interface Workspaces {
  data: Workspace1;
  model: Workspace1;
  training: Workspace1;
}
export interface Workspace1 {
  blocks: BlocklyBlocks;
}
export interface BlocklyBlocks {
  languageVersion?: Languageversion;
  blocks?: Blocks;
}
export interface Settings {
  dataDirectory?: Datadirectory;
  seed?: Seed;
  executionMode?: Executionmode;
}
export interface UI {
  activeTab?: Activetab;
  codeVisible?: Codevisible;
}
export interface SnapshotObject {
  blockId: Blockid1;
  kind: Kind1;
  role: Role;
  workspace: Workspace2;
  registered: Registered;
}
