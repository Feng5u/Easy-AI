/* Generated from Pydantic. Do not edit. */

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
