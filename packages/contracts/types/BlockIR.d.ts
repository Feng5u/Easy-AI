/* Generated from Pydantic. Do not edit. */

export type Typeid = string;
export type Blockid = string;
export type Workspace = "data" | "model" | "training";

export interface BlockIR {
  typeId: Typeid;
  origin: Origin;
  fields: Fields;
  inputs: Inputs;
}
export interface Origin {
  blockId: Blockid;
  workspace: Workspace;
}
export interface Fields {
  [k: string]: unknown;
}
export interface Inputs {
  [k: string]: BlockIR1[];
}
export interface BlockIR1 {
  typeId: Typeid;
  origin: Origin;
  fields: Fields;
  inputs: Inputs;
}
