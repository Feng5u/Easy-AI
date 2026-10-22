"""Validated semantic IR. Emitters accept these models, never raw Blockly fields."""

from typing import Annotated, Literal

from pydantic import Field

from easyai.domain.contracts import Contract, Origin, SymbolEntry

Identifier = Annotated[str, Field(pattern=r"^[A-Za-z][A-Za-z0-9_]*$", max_length=64)]

PositiveInt = Annotated[int, Field(ge=1, le=1_000_000)]


class TensorStep(Contract):
    kind: Literal["data.to_tensor"] = "data.to_tensor"
    origin: Origin


class NormalizeStep(Contract):
    kind: Literal["data.normalize"] = "data.normalize"
    origin: Origin
    mean: list[float] = Field(min_length=1, max_length=3)
    std: list[Annotated[float, Field(gt=0)]] = Field(min_length=1, max_length=3)


TransformStep = Annotated[TensorStep | NormalizeStep, Field(discriminator="kind")]


class TransformDef(Contract):
    id: str
    name: Identifier
    origin: Origin
    steps: list[TransformStep] = Field(min_length=1, max_length=2)


class DatasetDef(Contract):
    id: str
    name: Identifier
    origin: Origin
    dataset_name: Literal["MNIST", "FashionMNIST", "CIFAR10"]
    split: Literal["train", "test"]
    transform_id: str
    channels: Literal[1, 3]
    height: Literal[28, 32]
    width: Literal[28, 32]
    classes: Literal[10] = 10


class LoaderDef(Contract):
    id: str
    name: Identifier
    origin: Origin
    dataset_id: str
    batch_size: int = Field(ge=1, le=65536)
    shuffle: bool
    role: Literal["train", "test"]


class Conv2dSpec(Contract):
    kind: Literal["model.conv2d"] = "model.conv2d"
    origin: Origin
    in_channels: int = Field(ge=1, le=4096)
    out_channels: int = Field(ge=1, le=4096)
    kernel_size: int = Field(ge=1, le=127)
    padding: int = Field(ge=0, le=127)


class LinearSpec(Contract):
    kind: Literal["model.linear"] = "model.linear"
    origin: Origin
    in_features: PositiveInt
    out_features: PositiveInt


class ReluSpec(Contract):
    kind: Literal["model.relu"] = "model.relu"
    origin: Origin


class PoolSpec(Contract):
    kind: Literal["model.maxpool2d"] = "model.maxpool2d"
    origin: Origin
    kernel_size: int = Field(ge=1, le=127)


class DropoutSpec(Contract):
    kind: Literal["model.dropout"] = "model.dropout"
    origin: Origin
    p: float = Field(ge=0, lt=1)


AtomicLayer = Annotated[
    Conv2dSpec | LinearSpec | ReluSpec | PoolSpec | DropoutSpec, Field(discriminator="kind")
]


class SequentialSpec(Contract):
    kind: Literal["model.sequential"] = "model.sequential"
    origin: Origin
    layers: list[AtomicLayer] = Field(min_length=1)


class FlattenSpec(Contract):
    kind: Literal["model.flatten"] = "model.flatten"
    origin: Origin


LayerSpec = Annotated[
    Conv2dSpec | LinearSpec | ReluSpec | PoolSpec | DropoutSpec | SequentialSpec | FlattenSpec,
    Field(discriminator="kind"),
]


class ModelDef(Contract):
    id: str
    name: Identifier
    origin: Origin
    layers: list[LayerSpec] = Field(min_length=1)


class DataSourceSpec(Contract):
    origin: Origin
    source: Literal["train_loss", "test_accuracy", "train_samples", "test_samples", "predictions"]
    x_source: Literal["epoch", "none"]


class TitleSpec(Contract):
    origin: Origin
    text: str = Field(max_length=256)
    color: Literal["black", "red", "green", "blue"]


class AxisSpec(Contract):
    origin: Origin
    show_ticks: bool


class PanelSpec(Contract):
    origin: Origin
    chart_type: Literal["line", "scatter", "image_grid"]
    count: int = Field(ge=1, le=100)
    rows: int = Field(ge=1, le=10)
    cols: int = Field(ge=1, le=10)
    sources: list[DataSourceSpec] = Field(min_length=1)
    title: TitleSpec | None = None
    legend: Origin | None = None
    axis: AxisSpec | None = None


class SaveSpec(Contract):
    origin: Origin
    relative_path: str


class FigureSpec(Contract):
    id: str
    origin: Origin
    layout: list[int] = Field(min_length=2, max_length=2)
    size: Literal["small", "medium", "large"]
    panels: list[PanelSpec] = Field(min_length=1)
    save: SaveSpec | None = None


class TrainingSpec(Contract):
    origin: Origin
    model_id: str
    train_loader_id: str
    test_loader_id: str
    criterion: Literal["CrossEntropy"] = "CrossEntropy"
    optimizer: Literal["SGD", "Adam"]
    learning_rate: float = Field(gt=0, le=100)
    epochs: int = Field(ge=1, le=10000)
    before: list[FigureSpec]
    body: list[FigureSpec]
    after: list[FigureSpec]


class ShapeStep(Contract):
    origin: Origin
    input_shape: list[int]
    output_shape: list[int]


class ProgramIR(Contract):
    ir_version: Literal[1] = 1
    compiler_version: Literal["0.0.0"] = "0.0.0"
    block_library_version: Literal["0.0.0"] = "0.0.0"
    seed: int = Field(ge=0, le=4294967295)
    execution_mode: Literal["full", "quick"]
    symbols: list[SymbolEntry]
    transforms: list[TransformDef]
    datasets: list[DatasetDef]
    dataloaders: list[LoaderDef]
    model: ModelDef
    training: TrainingSpec
    imports: list[str]
    shape_trace: list[ShapeStep]
