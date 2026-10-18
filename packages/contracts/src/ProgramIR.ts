/* Generated from Pydantic. Do not edit. */

export type Irversion = 1;
export type Id = string;
export type Kind = "transform" | "dataset" | "dataloader" | "model_class";
export type Name = string;
export type Role = ("train" | "test") | null;
export type Workspace = "data" | "model";
export type Registered = boolean;
export type Symbols = SymbolEntry[];
export type Typeid = string;
export type Blockid = string;
export type Workspace1 = "data" | "model" | "training";
export type Transforms = BlockIR[];
export type Datasets = BlockIR[];
export type Dataloaders = BlockIR[];

export interface ProgramIR {
  irVersion?: Irversion;
  symbols: Symbols;
  transforms: Transforms;
  datasets: Datasets;
  dataloaders: Dataloaders;
  model: BlockIR;
  training: BlockIR;
}
export interface SymbolEntry {
  id: Id;
  kind: Kind;
  name: Name;
  role?: Role;
  workspace: Workspace;
  registered: Registered;
}
export interface BlockIR {
  typeId: Typeid;
  origin: Origin;
  fields: Fields;
  inputs: Inputs;
}
export interface Origin {
  blockId: Blockid;
  workspace: Workspace1;
}
export interface Fields {
  [k: string]: unknown;
}
export interface Inputs {
  [k: string]: BlockIR[];
}
