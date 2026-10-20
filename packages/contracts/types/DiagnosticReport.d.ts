/* Generated from Pydantic. Do not edit. */

export type Reportversion = 1;
export type Scope = "local_safe_summary";
export type Code = "RUNTIME_NAME_ERROR" | "RUNTIME_EXCEPTION";
export type Runid = string;
export type Eventseq = number;
export type Codehash = string;
export type Projectrevision = number;
export type Precision = "semantic" | "scaffold" | "none";
export type Namestate = "registered" | "unregistered" | "not_matched" | "ambiguous" | "unavailable";
export type Referencecheck = "passed" | "failed" | "unavailable";
export type Objectstotal = number | null;
export type Registeredtotal = number | null;

export interface DiagnosticReport {
  reportVersion?: Reportversion;
  scope?: Scope;
  code: Code;
  runId: Runid;
  eventSeq: Eventseq;
  codeHash: Codehash;
  projectRevision: Projectrevision;
  precision: Precision;
  nameState: Namestate;
  referenceCheck: Referencecheck;
  objectsTotal?: Objectstotal;
  registeredTotal?: Registeredtotal;
}
