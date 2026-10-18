/* Generated from Pydantic. Do not edit. */

export type Name = "MNIST" | "FashionMNIST" | "CIFAR10";
export type Dataroot = string;

export interface DatasetProbe {
  name: Name;
  dataRoot: Dataroot;
}
