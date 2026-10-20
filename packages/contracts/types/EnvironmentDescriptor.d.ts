/* Generated from Pydantic. Do not edit. */

export type Environmentid = string;
export type Kind = "conda" | "python";
export type Location = string;
export type Readonly = true;

export interface EnvironmentDescriptor {
  environmentId: Environmentid;
  kind: Kind;
  location: Location;
  readOnly?: Readonly;
}
