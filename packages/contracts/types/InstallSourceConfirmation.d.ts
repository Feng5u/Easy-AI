/* Generated from Pydantic. Do not edit. */

export type Previewid = string;
export type Previewhash = string;
export type Confirmed = true;

export interface InstallSourceConfirmation {
  previewId: Previewid;
  previewHash: Previewhash;
  confirmed: Confirmed;
}
