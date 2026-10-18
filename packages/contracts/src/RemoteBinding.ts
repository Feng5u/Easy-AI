/* Generated from Pydantic. Do not edit. */

export type Bindingid = string;
export type Projectid = string;
export type Connectionid = string;
export type Targetid = string;
export type Environmentid = string;
export type Databindingid = string;
export type Projectrevision = number;
export type Programhash = string;
export type Pythonexecutable = string;
export type Environmentprefix = string | null;
export type Device = "cpu" | "cuda" | "mps";
export type Datasetname = "MNIST" | "FashionMNIST" | "CIFAR10";
export type Dataroot = string;
export type Runbase = string;
export type Expiresinseconds = number;

export interface RemoteBinding {
  bindingId: Bindingid;
  projectId: Projectid;
  connectionId: Connectionid;
  targetId: Targetid;
  environmentId: Environmentid;
  dataBindingId: Databindingid;
  projectRevision: Projectrevision;
  programHash: Programhash;
  pythonExecutable: Pythonexecutable;
  environmentPrefix: Environmentprefix;
  device: Device;
  datasetName: Datasetname;
  dataRoot: Dataroot;
  runBase: Runbase;
  expiresInSeconds: Expiresinseconds;
}
