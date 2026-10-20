/* Generated from Pydantic. Do not edit. */

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
export type Requestid = number;

export interface CompileRequest {
  project: ProjectDocument;
  requestId: Requestid;
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
  data: Workspace;
  model: Workspace;
  training: Workspace;
}
export interface Workspace {
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
