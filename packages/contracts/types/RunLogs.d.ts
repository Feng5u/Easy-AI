/* Generated from Pydantic. Do not edit. */

export type Stdout = string;
export type Stderr = string;
export type Stdoutafter = number;
export type Stderrafter = number;
export type Done = boolean;

export interface RunLogs {
  stdout: Stdout;
  stderr: Stderr;
  stdoutAfter: Stdoutafter;
  stderrAfter: Stderrafter;
  done: Done;
}
