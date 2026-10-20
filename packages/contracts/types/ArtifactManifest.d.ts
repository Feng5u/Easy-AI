/* Generated from Pydantic. Do not edit. */

export type Protocolversion = 1;
export type Projectid = string;
export type Targetid = string;
export type Runid = string;
export type Launchid = string;
export type Username = string;
export type Host = string;
export type Port = number;
export type Hostfingerprint = string;
export type Runroot = string;
export type Programhash = string;
export type Codehash = string;
export type Bundlehash = string;
export type Confighash = string;
export type Uid = number;
export type Sourceseq = number;
export type Eventssha256 = string;
export type Artifactid = string;
export type Runid1 = string;
export type Kind = "figure" | "model" | "log" | "metrics";
export type Relativepath = string;
export type Mimetype = string;
export type Sizebytes = number;
export type Sha256 = string;
export type Producerblockid = string;
export type Contributorblockids = string[];
export type Phase = ("before" | "epoch_end" | "after") | null;
export type Epoch = number | null;
export type Syncstate = "pending" | "syncing" | "ready" | "error";
/**
 * @maxItems 256
 */
export type Artifacts = ArtifactRecord[];

export interface ArtifactManifest {
  protocolVersion?: Protocolversion;
  identity: RemoteRunIdentity;
  uid: Uid;
  sourceSeq: Sourceseq;
  eventsSha256: Eventssha256;
  artifacts: Artifacts;
}
export interface RemoteRunIdentity {
  projectId: Projectid;
  targetId: Targetid;
  runId: Runid;
  launchId: Launchid;
  username: Username;
  endpoint: SshEndpoint;
  hostFingerprint: Hostfingerprint;
  runRoot: Runroot;
  programHash: Programhash;
  codeHash: Codehash;
  bundleHash: Bundlehash;
  configHash: Confighash;
}
export interface SshEndpoint {
  host: Host;
  port?: Port;
}
export interface ArtifactRecord {
  artifactId: Artifactid;
  runId: Runid1;
  kind: Kind;
  relativePath: Relativepath;
  mimeType: Mimetype;
  sizeBytes: Sizebytes;
  sha256: Sha256;
  producerBlockId: Producerblockid;
  contributorBlockIds: Contributorblockids;
  phase?: Phase;
  epoch?: Epoch;
  syncState: Syncstate;
}
