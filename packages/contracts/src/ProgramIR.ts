/* Generated from Pydantic. Do not edit. */

export type Irversion = 1;
export type Compilerversion = "0.0.0";
export type Blocklibraryversion = "0.0.0";
export type Seed = number;
export type Executionmode = "full" | "quick";
export type Id = string;
export type Kind = "transform" | "dataset" | "dataloader" | "model_class";
export type Name = string;
export type Role = ("train" | "test") | null;
export type Workspace = "data" | "model";
export type Registered = boolean;
export type Symbols = SymbolEntry[];
export type Id1 = string;
export type Name1 = string;
export type Blockid = string;
export type Workspace1 = "data" | "model" | "training";
/**
 * @minItems 1
 * @maxItems 2
 */
export type Steps = [TensorStep | NormalizeStep] | [TensorStep | NormalizeStep, TensorStep | NormalizeStep];
export type Kind1 = "data.to_tensor";
export type Kind2 = "data.normalize";
/**
 * @minItems 1
 * @maxItems 3
 */
export type Mean = [number] | [number, number] | [number, number, number];
/**
 * @minItems 1
 * @maxItems 3
 */
export type Std = [number] | [number, number] | [number, number, number];
export type Transforms = TransformDef[];
export type Id2 = string;
export type Name2 = string;
export type Datasetname = "MNIST" | "FashionMNIST" | "CIFAR10";
export type Split = "train" | "test";
export type Transformid = string;
export type Channels = 1 | 3;
export type Height = 28 | 32;
export type Width = 28 | 32;
export type Classes = 10;
export type Datasets = DatasetDef[];
export type Id3 = string;
export type Name3 = string;
export type Datasetid = string;
export type Batchsize = number;
export type Shuffle = boolean;
export type Role1 = "train" | "test";
export type Dataloaders = LoaderDef[];
export type Id4 = string;
export type Name4 = string;
/**
 * @minItems 1
 */
export type Layers = [
  Conv2DSpec | LinearSpec | ReluSpec | PoolSpec | DropoutSpec | SequentialSpec | FlattenSpec,
  ...(Conv2DSpec | LinearSpec | ReluSpec | PoolSpec | DropoutSpec | SequentialSpec | FlattenSpec)[]
];
export type Kind3 = "model.conv2d";
export type Inchannels = number;
export type Outchannels = number;
export type Kernelsize = number;
export type Padding = number;
export type Kind4 = "model.linear";
export type Infeatures = number;
export type Outfeatures = number;
export type Kind5 = "model.relu";
export type Kind6 = "model.maxpool2d";
export type Kernelsize1 = number;
export type Kind7 = "model.dropout";
export type P = number;
export type Kind8 = "model.sequential";
/**
 * @minItems 1
 */
export type Layers1 = [
  Conv2DSpec | LinearSpec | ReluSpec | PoolSpec | DropoutSpec,
  ...(Conv2DSpec | LinearSpec | ReluSpec | PoolSpec | DropoutSpec)[]
];
export type Kind9 = "model.flatten";
export type Modelid = string;
export type Trainloaderid = string;
export type Testloaderid = string;
export type Criterion = "CrossEntropy";
export type Optimizer = "SGD" | "Adam";
export type Learningrate = number;
export type Epochs = number;
export type Id5 = string;
/**
 * @minItems 2
 * @maxItems 2
 */
export type Layout = [number, number];
export type Size = "small" | "medium" | "large";
/**
 * @minItems 1
 */
export type Panels = [PanelSpec, ...PanelSpec[]];
export type Charttype = "line" | "scatter" | "image_grid";
export type Count = number;
export type Rows = number;
export type Cols = number;
/**
 * @minItems 1
 */
export type Sources = [DataSourceSpec, ...DataSourceSpec[]];
export type Source = "train_loss" | "test_accuracy" | "train_samples" | "test_samples" | "predictions";
export type Xsource = "epoch" | "none";
export type Text = string;
export type Color = "black" | "red" | "green" | "blue";
export type Showticks = boolean;
export type Relativepath = string;
export type Before = FigureSpec[];
export type Body = FigureSpec[];
export type After = FigureSpec[];
export type Imports = string[];
export type Inputshape = number[];
export type Outputshape = number[];
export type Shapetrace = ShapeStep[];

export interface ProgramIR {
  irVersion?: Irversion;
  compilerVersion?: Compilerversion;
  blockLibraryVersion?: Blocklibraryversion;
  seed: Seed;
  executionMode: Executionmode;
  symbols: Symbols;
  transforms: Transforms;
  datasets: Datasets;
  dataloaders: Dataloaders;
  model: ModelDef;
  training: TrainingSpec;
  imports: Imports;
  shapeTrace: Shapetrace;
}
export interface SymbolEntry {
  id: Id;
  kind: Kind;
  name: Name;
  role?: Role;
  workspace: Workspace;
  registered: Registered;
}
export interface TransformDef {
  id: Id1;
  name: Name1;
  origin: Origin;
  steps: Steps;
}
export interface Origin {
  blockId: Blockid;
  workspace: Workspace1;
}
export interface TensorStep {
  kind?: Kind1;
  origin: Origin;
}
export interface NormalizeStep {
  kind?: Kind2;
  origin: Origin;
  mean: Mean;
  std: Std;
}
export interface DatasetDef {
  id: Id2;
  name: Name2;
  origin: Origin;
  datasetName: Datasetname;
  split: Split;
  transformId: Transformid;
  channels: Channels;
  height: Height;
  width: Width;
  classes?: Classes;
}
export interface LoaderDef {
  id: Id3;
  name: Name3;
  origin: Origin;
  datasetId: Datasetid;
  batchSize: Batchsize;
  shuffle: Shuffle;
  role: Role1;
}
export interface ModelDef {
  id: Id4;
  name: Name4;
  origin: Origin;
  layers: Layers;
}
export interface Conv2DSpec {
  kind?: Kind3;
  origin: Origin;
  inChannels: Inchannels;
  outChannels: Outchannels;
  kernelSize: Kernelsize;
  padding: Padding;
}
export interface LinearSpec {
  kind?: Kind4;
  origin: Origin;
  inFeatures: Infeatures;
  outFeatures: Outfeatures;
}
export interface ReluSpec {
  kind?: Kind5;
  origin: Origin;
}
export interface PoolSpec {
  kind?: Kind6;
  origin: Origin;
  kernelSize: Kernelsize1;
}
export interface DropoutSpec {
  kind?: Kind7;
  origin: Origin;
  p: P;
}
export interface SequentialSpec {
  kind?: Kind8;
  origin: Origin;
  layers: Layers1;
}
export interface FlattenSpec {
  kind?: Kind9;
  origin: Origin;
}
export interface TrainingSpec {
  origin: Origin;
  modelId: Modelid;
  trainLoaderId: Trainloaderid;
  testLoaderId: Testloaderid;
  criterion?: Criterion;
  optimizer: Optimizer;
  learningRate: Learningrate;
  epochs: Epochs;
  before: Before;
  body: Body;
  after: After;
}
export interface FigureSpec {
  id: Id5;
  origin: Origin;
  layout: Layout;
  size: Size;
  panels: Panels;
  save?: SaveSpec | null;
}
export interface PanelSpec {
  origin: Origin;
  chartType: Charttype;
  count: Count;
  rows: Rows;
  cols: Cols;
  sources: Sources;
  title?: TitleSpec | null;
  legend?: Origin | null;
  axis?: AxisSpec | null;
}
export interface DataSourceSpec {
  origin: Origin;
  source: Source;
  xSource: Xsource;
}
export interface TitleSpec {
  origin: Origin;
  text: Text;
  color: Color;
}
export interface AxisSpec {
  origin: Origin;
  showTicks: Showticks;
}
export interface SaveSpec {
  origin: Origin;
  relativePath: Relativepath;
}
export interface ShapeStep {
  origin: Origin;
  inputShape: Inputshape;
  outputShape: Outputshape;
}
