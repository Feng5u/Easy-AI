/* Generated from Pydantic. Do not edit. */

export type Expectedrevision = number;
export type Expectedprogramhash = string;
export type Pythonselectionid = string;
export type Dataselectionid = string;

export interface RunStartRequest {
  expectedRevision: Expectedrevision;
  expectedProgramHash: Expectedprogramhash;
  pythonSelectionId: Pythonselectionid;
  dataSelectionId: Dataselectionid;
}
