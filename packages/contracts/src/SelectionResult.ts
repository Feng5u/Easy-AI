/* Generated from Pydantic. Do not edit. */

export type Selectionid = string;
export type Kind = "project" | "python" | "data";
export type Label = string;

export interface SelectionResult {
  selectionId: Selectionid;
  kind: Kind;
  label: Label;
}
