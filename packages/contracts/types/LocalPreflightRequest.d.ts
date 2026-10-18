/* Generated from Pydantic. Do not edit. */

export type Projectid = string;
export type Expectedrevision = number;
export type Pythonselectionid = string;
export type Dataselectionid = string;

export interface LocalPreflightRequest {
  projectId: Projectid;
  expectedRevision: Expectedrevision;
  pythonSelectionId: Pythonselectionid;
  dataSelectionId: Dataselectionid;
}
