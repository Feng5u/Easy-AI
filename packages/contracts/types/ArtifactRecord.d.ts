/* Generated from Pydantic. Do not edit. */

export type Artifactid = string;
export type Runid = string;
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

export interface ArtifactRecord {
  artifactId: Artifactid;
  runId: Runid;
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
