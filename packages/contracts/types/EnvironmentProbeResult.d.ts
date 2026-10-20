/* Generated from Pydantic. Do not edit. */

export type Projectid = string;
export type Connectionid = string;
export type Requestid = string;
export type Projectid1 = string;
export type Connectionid1 = string;
export type Host = string;
export type Port = number;
export type Hostfingerprint = string;
export type Environmentid = string;
export type Schemaversion = 1;
export type Nonce = string;
export type Platform = "linux";
export type Executable = string;
export type Prefix = string;
/**
 * @minItems 3
 * @maxItems 3
 */
export type Version = [number, number, number];
export type Version1 = string | null;
export type Imported = boolean;
export type Error = ("missing" | "import_failed") | null;
export type Cudaavailable = boolean | null;
export type Mpsavailable = boolean | null;
export type Attempted = boolean;
export type Ok = boolean;
export type Device = "cpu" | "cuda" | "mps";
export type Error1 = ("dependency_missing" | "device_unavailable" | "execution_failed") | null;
export type Name = "MNIST" | "FashionMNIST" | "CIFAR10";
export type Dataroot = string;
export type Ok1 = boolean;
export type Sampleshape =
  [] | [number] | [number, number] | [number, number, number] | [number, number, number, number] | null;
export type Sampledtype = string | null;
export type Label = number | null;
export type Error2 = ("dependency_missing" | "unavailable" | "unsafe_format_blocked") | null;
export type Environmentready = boolean;
export type Dataready = boolean | null;
/**
 * @maxItems 6
 */
export type Issues =
  | []
  | [ProbeIssue]
  | [ProbeIssue, ProbeIssue]
  | [ProbeIssue, ProbeIssue, ProbeIssue]
  | [ProbeIssue, ProbeIssue, ProbeIssue, ProbeIssue]
  | [ProbeIssue, ProbeIssue, ProbeIssue, ProbeIssue, ProbeIssue]
  | [ProbeIssue, ProbeIssue, ProbeIssue, ProbeIssue, ProbeIssue, ProbeIssue];
export type Code =
  | "PYTHON_UNSUPPORTED"
  | "TORCH_IMPORT_FAILED"
  | "TORCHVISION_IMPORT_FAILED"
  | "MATPLOTLIB_IMPORT_FAILED"
  | "TENSOR_CHECK_FAILED"
  | "DATASET_CHECK_FAILED";
export type Suggestion = string;

export interface EnvironmentProbeResult {
  projectId: Projectid;
  connectionId: Connectionid;
  requestId: Requestid;
  scope: EnvironmentScope;
  environmentId: Environmentid;
  report: EnvironmentProbeReport;
  environmentReady: Environmentready;
  dataReady: Dataready;
  issues: Issues;
}
export interface EnvironmentScope {
  projectId: Projectid1;
  connectionId: Connectionid1;
  endpoint: SshEndpoint;
  hostFingerprint: Hostfingerprint;
}
export interface SshEndpoint {
  host: Host;
  port?: Port;
}
export interface EnvironmentProbeReport {
  schemaVersion: Schemaversion;
  nonce: Nonce;
  platform: Platform;
  python: PythonCheck;
  imports: ImportChecks;
  devices: DeviceCheck;
  tensor: TensorCheck;
  dataset: DatasetCheck | null;
}
export interface PythonCheck {
  executable: Executable;
  prefix: Prefix;
  version: Version;
}
export interface ImportChecks {
  torch: PackageCheck;
  torchvision: PackageCheck;
  matplotlib: PackageCheck;
}
export interface PackageCheck {
  version: Version1;
  imported: Imported;
  error: Error;
}
export interface DeviceCheck {
  cudaAvailable: Cudaavailable;
  mpsAvailable: Mpsavailable;
}
export interface TensorCheck {
  attempted: Attempted;
  ok: Ok;
  device: Device;
  error: Error1;
}
export interface DatasetCheck {
  name: Name;
  dataRoot: Dataroot;
  ok: Ok1;
  sampleShape: Sampleshape;
  sampleDtype: Sampledtype;
  label: Label;
  error: Error2;
}
export interface ProbeIssue {
  code: Code;
  suggestion: Suggestion;
}
