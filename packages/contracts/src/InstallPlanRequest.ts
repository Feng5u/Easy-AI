/* Generated from Pydantic. Do not edit. */

export type Targetid = "local" | string;
export type Projectid = string;
export type Connectionid = string;
export type Profileid = "teacher-existing" | "easyai-cpu";
/**
 * @minItems 1
 * @maxItems 17
 */
export type Packageids =
  | [string]
  | [string, string]
  | [string, string, string]
  | [string, string, string, string]
  | [string, string, string, string, string]
  | [string, string, string, string, string, string]
  | [string, string, string, string, string, string, string]
  | [string, string, string, string, string, string, string, string]
  | [string, string, string, string, string, string, string, string, string]
  | [string, string, string, string, string, string, string, string, string, string]
  | [string, string, string, string, string, string, string, string, string, string, string]
  | [string, string, string, string, string, string, string, string, string, string, string, string]
  | [string, string, string, string, string, string, string, string, string, string, string, string, string]
  | [string, string, string, string, string, string, string, string, string, string, string, string, string, string]
  | [
      string,
      string,
      string,
      string,
      string,
      string,
      string,
      string,
      string,
      string,
      string,
      string,
      string,
      string,
      string
    ]
  | [
      string,
      string,
      string,
      string,
      string,
      string,
      string,
      string,
      string,
      string,
      string,
      string,
      string,
      string,
      string,
      string
    ]
  | [
      string,
      string,
      string,
      string,
      string,
      string,
      string,
      string,
      string,
      string,
      string,
      string,
      string,
      string,
      string,
      string,
      string
    ];
export type Ownedenvironmentid = string | null;
export type Name = string;

export interface InstallPlanRequest {
  targetId: Targetid;
  remoteSession?: SessionControl | null;
  profileId: Profileid;
  packageIds: Packageids;
  ownedEnvironmentId?: Ownedenvironmentid;
  newEnvironmentSpec?: NewEnvironmentSpec | null;
}
export interface SessionControl {
  projectId: Projectid;
  connectionId: Connectionid;
}
export interface NewEnvironmentSpec {
  name: Name;
}
