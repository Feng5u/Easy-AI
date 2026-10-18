/* Generated from Pydantic. Do not edit. */

export type Challengeid = string;
export type Fingerprint = string;

export interface HostKeyConfirmation {
  challengeId: Challengeid;
  fingerprint: Fingerprint;
}
