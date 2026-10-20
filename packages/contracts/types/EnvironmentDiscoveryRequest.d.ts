/* Generated from Pydantic. Do not edit. */

export type Projectid = string;
export type Connectionid = string;
export type Requestid = string;
export type Condapath = string | null;
export type Pythonpath = string | null;

export interface EnvironmentDiscoveryRequest {
  projectId: Projectid;
  connectionId: Connectionid;
  requestId: Requestid;
  condaPath?: Condapath;
  pythonPath?: Pythonpath;
}
