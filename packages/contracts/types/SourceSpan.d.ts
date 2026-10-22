/* Generated from Pydantic. Do not edit. */

export type File = "train.py";
export type Startline = number;
export type Endline = number;
export type Blockid = string;
export type Workspace = "data" | "model" | "training";
export type Kind = "semantic" | "scaffold";

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
