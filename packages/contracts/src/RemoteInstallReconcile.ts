/* Generated from Pydantic. Do not edit. */

export type Projectid = string;
export type Connectionid = string;
export type Cancel = boolean;

export interface RemoteInstallReconcile {
  session: SessionControl;
  cancel?: Cancel;
}
export interface SessionControl {
  projectId: Projectid;
  connectionId: Connectionid;
}
