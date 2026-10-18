/* Generated from Pydantic. Do not edit. */

export type Revision = number;
export type Programhash = string;
export type Compilerversion = string;
export type Code = string;
export type Severity = "error" | "warning" | "info";
export type Message = string;
export type Blockid = string;
export type Workspace = "data" | "model" | "training";
export type Field = string | null;
export type Suggestion = string | null;
export type Details = {
  [k: string]: unknown;
} | null;
export type Diagnostics = Diagnostic[];
export type Runnable = boolean;
export type Code1 = string | null;
export type Codehash = string | null;
export type Sourcemap = SourceSpan[] | null;
export type File = "train.py";
export type Startline = number;
export type Endline = number;
export type Kind = "semantic" | "scaffold";
export type Requestid = number;

export interface CompileResponse {
  revision: Revision;
  programHash: Programhash;
  compilerVersion?: Compilerversion;
  diagnostics: Diagnostics;
  runnable: Runnable;
  code?: Code1;
  codeHash?: Codehash;
  sourceMap?: Sourcemap;
  requestId: Requestid;
}
export interface Diagnostic {
  code: Code;
  severity?: Severity;
  message: Message;
  origin?: Origin | null;
  field?: Field;
  suggestion?: Suggestion;
  details?: Details;
}
export interface Origin {
  blockId: Blockid;
  workspace: Workspace;
}
export interface SourceSpan {
  file?: File;
  startLine: Startline;
  endLine: Endline;
  origin: Origin;
  kind: Kind;
}
