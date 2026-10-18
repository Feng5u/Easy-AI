/* Generated from Pydantic. Do not edit. */

export type Projectid = string;
export type Expectedrevision = number;
export type Pythonselectionid = string;
export type Dataselectionid = string;
export type Ok = boolean;
export type Code = string;
export type Python = string;
export type Prefix = string;
export type Torch = string;
export type Torchvision = string;
export type Matplotlib = string;
export type Datasetnames = string[];

export interface LocalPreflightResult {
  projectId: Projectid;
  expectedRevision: Expectedrevision;
  pythonSelectionId: Pythonselectionid;
  dataSelectionId: Dataselectionid;
  environment: LocalPreflightCheck;
  data: LocalPreflightCheck;
  versions?: LocalPythonVersions | null;
  datasetNames: Datasetnames;
}
export interface LocalPreflightCheck {
  ok: Ok;
  code: Code;
}
export interface LocalPythonVersions {
  python: Python;
  prefix: Prefix;
  torch: Torch;
  torchvision: Torchvision;
  matplotlib: Matplotlib;
}
