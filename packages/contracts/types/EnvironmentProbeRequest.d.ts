/* Generated from Pydantic. Do not edit. */

export type Projectid = string;
export type Connectionid = string;
export type Requestid = string;
export type Environmentid = string;
export type Device = "cpu" | "cuda" | "mps";
export type Name = "MNIST" | "FashionMNIST" | "CIFAR10";
export type Dataroot = string;

export interface EnvironmentProbeRequest {
  projectId: Projectid;
  connectionId: Connectionid;
  requestId: Requestid;
  environmentId: Environmentid;
  device?: Device;
  dataset?: DatasetProbe | null;
}
export interface DatasetProbe {
  name: Name;
  dataRoot: Dataroot;
}
