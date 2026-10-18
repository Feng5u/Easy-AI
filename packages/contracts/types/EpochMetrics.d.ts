/* Generated from Pydantic. Do not edit. */

export type Epoch = number;
export type Trainloss = number;
export type Testaccuracy = number;
export type Trainsamples = number;
export type Testsamples = number;
export type Elapsedseconds = number;

export interface EpochMetrics {
  epoch: Epoch;
  trainLoss: Trainloss;
  testAccuracy: Testaccuracy;
  trainSamples: Trainsamples;
  testSamples: Testsamples;
  elapsedSeconds: Elapsedseconds;
}
