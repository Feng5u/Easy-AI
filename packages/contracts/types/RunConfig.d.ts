/* Generated from Pydantic. Do not edit. */

export type Configversion = 1;
export type Runid = string;
export type Projectid = string;
export type Projectrevision = number;
export type Programhash = string;
export type Codehash = string;
export type Bundlehash = string;
export type Targetid = string;
export type Runner = "local" | "ssh";
export type Dataroot = string;
export type Runroot = string;
export type Pythonexecutable = string;
export type Environmentprefix = string | null;
export type Executionmode = "full" | "quick";
export type Seed = number;
export type Numworkers = number;
export type Pinmemorypolicy = "cuda_only";
export type Epochs = 1;
export type Trainsamples = 1024;
export type Testsamples = 256;

export interface RunConfig {
  configVersion?: Configversion;
  runId: Runid;
  projectId: Projectid;
  projectRevision: Projectrevision;
  programHash: Programhash;
  codeHash: Codehash;
  bundleHash: Bundlehash;
  targetId: Targetid;
  runner: Runner;
  dataRoot: Dataroot;
  runRoot: Runroot;
  pythonExecutable: Pythonexecutable;
  environmentPrefix?: Environmentprefix;
  executionMode: Executionmode;
  seed: Seed;
  numWorkers: Numworkers;
  pinMemoryPolicy?: Pinmemorypolicy;
  quickLimits?: QuickLimits | null;
}
export interface QuickLimits {
  epochs?: Epochs;
  trainSamples?: Trainsamples;
  testSamples?: Testsamples;
}
