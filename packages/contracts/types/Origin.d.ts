/* Generated from Pydantic. Do not edit. */

export type Blockid = string;
export type Workspace = "data" | "model" | "training";

export interface Origin {
  blockId: Blockid;
  workspace: Workspace;
}
