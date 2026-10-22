/* Generated from Pydantic. Do not edit. */

export type Id = string;
export type Kind = "transform" | "dataset" | "dataloader" | "model_class";
export type Name = string;
export type Role = ("train" | "test") | null;
export type Workspace = "data" | "model";
export type Registered = boolean;

export interface SymbolEntry {
  id: Id;
  kind: Kind;
  name: Name;
  role?: Role;
  workspace: Workspace;
  registered: Registered;
}
