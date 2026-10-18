/* Generated from Pydantic. Do not edit. */

export type Protocolversion = 1;
export type Runid = string;
export type Seq = number;
export type Source = "runtime" | "application";
export type Sourceseq = number | null;
export type Timestamp = string;
export type Type =
  | "runtime_started"
  | "device_selected"
  | "progress"
  | "epoch_completed"
  | "artifact_created"
  | "runtime_error"
  | "pipeline_cancelled"
  | "pipeline_completed"
  | "process_exited"
  | "status_changed";
export type Blockid = string | null;

export interface Event {
  protocolVersion?: Protocolversion;
  runId: Runid;
  seq: Seq;
  source: Source;
  sourceSeq?: Sourceseq;
  timestamp: Timestamp;
  type: Type;
  blockId?: Blockid;
  payload: Payload;
}
export interface Payload {
  [k: string]: unknown;
}
