"""Authority boundary: manifest-validated BlockIR -> typed semantic ProgramIR."""

import math
from typing import Literal

from pydantic import ValidationError

from easyai.domain.catalog import definitions
from easyai.domain.contracts import BlockIR, Diagnostic, ProjectDocument, SymbolEntry
from easyai.domain.program import (
    AtomicLayer,
    AxisSpec,
    Conv2dSpec,
    DataSourceSpec,
    DatasetDef,
    DropoutSpec,
    FigureSpec,
    FlattenSpec,
    LayerSpec,
    LinearSpec,
    LoaderDef,
    ModelDef,
    NormalizeStep,
    PanelSpec,
    PoolSpec,
    ProgramIR,
    ReluSpec,
    SaveSpec,
    SequentialSpec,
    ShapeStep,
    TensorStep,
    TitleSpec,
    TrainingSpec,
    TransformDef,
    TransformStep,
)
from easyai.security.paths import artifact_relative_path


class SemanticError(ValueError):
    def __init__(self, node: BlockIR, code: str, message: str, field: str | None = None):
        self.diagnostic = Diagnostic(code=code, message=message, origin=node.origin, field=field)
        super().__init__(code)


def lower_atomic(node: BlockIR) -> AtomicLayer:
    fields = node.fields
    match node.type_id:
        case "model.conv2d":
            return Conv2dSpec(
                origin=node.origin,
                in_channels=fields["IN_CHANNELS"],
                out_channels=fields["OUT_CHANNELS"],
                kernel_size=fields["KERNEL_SIZE"],
                padding=fields["PADDING"],
            )
        case "model.linear":
            return LinearSpec(
                origin=node.origin,
                in_features=fields["IN_FEATURES"],
                out_features=fields["OUT_FEATURES"],
            )
        case "model.relu":
            return ReluSpec(origin=node.origin)
        case "model.maxpool2d":
            return PoolSpec(origin=node.origin, kernel_size=fields["KERNEL_SIZE"])
        case "model.dropout":
            return DropoutSpec(origin=node.origin, p=fields["P"])
        case _:
            raise SemanticError(node, "PLACEMENT_INVALID", "顺序组合不支持这个模型节点。")


def lower_layer(node: BlockIR) -> LayerSpec:
    if node.type_id == "model.flatten":
        return FlattenSpec(origin=node.origin)
    if node.type_id == "model.sequential":
        if not node.inputs["layers"]:
            raise SemanticError(node, "MODEL_EMPTY", "顺序组合至少需要一层。")
        return SequentialSpec(
            origin=node.origin, layers=[lower_atomic(n) for n in node.inputs["layers"]]
        )
    return lower_atomic(node)


def lower_figure(node: BlockIR, phase: Literal["before", "body", "after"]) -> FigureSpec:
    panels: list[PanelSpec] = []
    layout = [int(x) for x in node.fields["LAYOUT"].split(",")]
    if not node.inputs["panels"] or len(node.inputs["panels"]) > math.prod(layout):
        raise SemanticError(
            node, "FIGURE_LAYOUT_INVALID", "画布至少需要一个子图，且不能超过格子数。"
        )
    for panel in node.inputs["panels"]:
        styles = panel.inputs["style"]
        if len({style.type_id for style in styles}) != len(styles):
            raise SemanticError(
                panel, "FIGURE_STYLE_DUPLICATED", "每个子图的标题、图例、坐标轴样式最多一个。"
            )
        title: TitleSpec | None = None
        axis: AxisSpec | None = None
        legend = None
        for style in styles:
            if style.type_id == "viz.title":
                title = TitleSpec(
                    origin=style.origin, text=style.fields["TEXT"], color=style.fields["COLOR"]
                )
            elif style.type_id == "viz.axis":
                axis = AxisSpec(origin=style.origin, show_ticks=style.fields["SHOW_TICKS"])
            else:
                legend = style.origin
        chart = panel.fields["CHART_TYPE"]
        sources: list[DataSourceSpec] = []
        for source in panel.inputs["data"]:
            source_name = source.fields["SOURCE"]
            x_source = source.fields["X_SOURCE"]
            is_metric = source_name in ("train_loss", "test_accuracy")
            if (chart == "image_grid") == is_metric:
                raise SemanticError(
                    source,
                    "VIZ_SOURCE_MISMATCH",
                    "图像网格需要样本来源，数值图需要损失或测试准确率。",
                    "SOURCE",
                )
            if x_source != ("epoch" if is_metric else "none"):
                raise SemanticError(
                    source,
                    "VIZ_SOURCE_MISMATCH",
                    "数值图横轴为epoch；样本图不接受数值横轴。",
                    "X_SOURCE",
                )
            if phase == "before" and (source_name == "predictions" or is_metric):
                raise SemanticError(
                    source, "VIZ_PHASE_INVALID", "训练前尚未产生预测或训练指标。", "SOURCE"
                )
            sources.append(
                DataSourceSpec(origin=source.origin, source=source_name, x_source=x_source)
            )
        if not sources:
            raise SemanticError(panel, "VIZ_SOURCE_MISSING", "请为子图选择数据来源。")
        if chart == "image_grid" and (len(sources) != 1 or legend is not None):
            raise SemanticError(
                panel, "VIZ_SOURCE_MISMATCH", "图像网格只使用一个样本来源，且不使用曲线图例。"
            )
        if (
            chart == "image_grid"
            and panel.fields["COUNT"] > panel.fields["ROWS"] * panel.fields["COLS"]
        ):
            raise SemanticError(
                panel, "FIGURE_LAYOUT_INVALID", "样本数量超过图像网格容量。", "COUNT"
            )
        panels.append(
            PanelSpec(
                origin=panel.origin,
                chart_type=chart,
                count=panel.fields["COUNT"],
                rows=panel.fields["ROWS"],
                cols=panel.fields["COLS"],
                sources=sources,
                title=title,
                legend=legend,
                axis=axis,
            )
        )
    saves = node.inputs["save"]
    if len(saves) > 1:
        raise SemanticError(node, "FIGURE_SAVE_DUPLICATED", "一张画布只能配置一个保存图像积木。")
    save = None
    if saves:
        try:
            path = artifact_relative_path(saves[0].fields["PATH"])
        except ValueError:
            raise SemanticError(
                saves[0], "OUTPUT_PATH_FORBIDDEN", "图像位置必须是输出目录内的相对PNG路径。", "PATH"
            ) from None
        save = SaveSpec(origin=saves[0].origin, relative_path=path)
    return FigureSpec(
        id=node.origin.block_id,
        origin=node.origin,
        layout=layout,
        size=node.fields["SIZE"],
        panels=panels,
        save=save,
    )


def shape_check(model: ModelDef, dataset: DatasetDef) -> tuple[list[ShapeStep], list[Diagnostic]]:
    trace: list[ShapeStep] = []
    errors: list[Diagnostic] = []
    shape: list[int] = [dataset.channels, dataset.height, dataset.width]

    def apply(layer: LayerSpec, before: list[int]) -> list[int]:
        after = before.copy()
        valid = True
        if isinstance(layer, SequentialSpec):
            for child in layer.layers:
                after = apply(child, after)
                if errors:
                    return after
        elif isinstance(layer, Conv2dSpec):
            valid = len(before) == 3 and before[0] == layer.in_channels
            if valid:
                after = [
                    layer.out_channels,
                    before[1] + 2 * layer.padding - layer.kernel_size + 1,
                    before[2] + 2 * layer.padding - layer.kernel_size + 1,
                ]
        elif isinstance(layer, PoolSpec):
            valid = len(before) == 3
            if valid:
                after = [before[0], before[1] // layer.kernel_size, before[2] // layer.kernel_size]
        elif isinstance(layer, FlattenSpec):
            after = [math.prod(before)]
        elif isinstance(layer, LinearSpec):
            valid = bool(before) and before[-1] == layer.in_features
            if valid:
                after[-1] = layer.out_features
        valid = valid and all(n > 0 for n in after)
        if not valid:
            errors.append(
                Diagnostic(
                    code="SHAPE_MISMATCH",
                    message=f"上一层输出为{before}，当前层输入参数不匹配。",
                    origin=layer.origin,
                    suggestion="核对通道、空间尺寸或inFeatures；不会自动修补。",
                )
            )
        trace.append(ShapeStep(origin=layer.origin, input_shape=before, output_shape=after))
        return after

    for layer in model.layers:
        shape = apply(layer, shape)
        if errors:
            break
    if not errors and shape != [dataset.classes]:
        errors.append(
            Diagnostic(
                code="SHAPE_MISMATCH",
                message=f"十分类模型需要输出[N,10]，当前为[N,{','.join(map(str, shape))}]。",
                origin=model.layers[-1].origin,
            )
        )
    return trace, errors


def lower_program(
    project: ProjectDocument, roots: list[BlockIR], symbols: list[SymbolEntry]
) -> tuple[ProgramIR | None, list[Diagnostic]]:
    index = {node.origin.block_id: node for node in roots}
    used: dict[str, BlockIR] = {}
    visiting: set[str] = set()
    reference_keys = {
        "data.dataloader": ["DATASET_REF"],
        "data.dataset_builtin": ["TRANSFORM_REF"],
        "train.loop": ["MODEL_REF", "TRAIN_LOADER_REF", "TEST_LOADER_REF"],
    }

    def require(node: BlockIR) -> None:
        identity = node.origin.block_id
        if identity in visiting:
            raise SemanticError(node, "REF_CYCLE", "引用形成循环。")
        if identity in used:
            return
        visiting.add(identity)
        for key in reference_keys.get(node.type_id, []):
            target = index.get(node.fields[key])
            if target is None:
                raise SemanticError(node, "REF_NOT_FOUND", "选择的对象不存在。", key)
            require(target)
        visiting.remove(identity)
        used[identity] = node

    training_node = next(node for node in roots if node.type_id == "train.loop")
    try:
        require(training_node)
        datasets: list[DatasetDef] = []
        for node in used.values():
            if node.type_id == "data.dataset_builtin":
                rgb = node.fields["DATASET_NAME"] == "CIFAR10"
                datasets.append(
                    DatasetDef(
                        id=node.origin.block_id,
                        name=node.fields["NAME"],
                        origin=node.origin,
                        dataset_name=node.fields["DATASET_NAME"],
                        split=node.fields["SPLIT"],
                        transform_id=node.fields["TRANSFORM_REF"],
                        channels=3 if rgb else 1,
                        height=32 if rgb else 28,
                        width=32 if rgb else 28,
                    )
                )
        datasets.sort(key=lambda item: (item.split != "train", item.id))
        if len(datasets) != 2 or datasets[0].split != "train" or datasets[1].split != "test":
            raise SemanticError(training_node, "ROLE_MISMATCH", "需要分别绑定训练和测试Dataset。")
        if (datasets[0].channels, datasets[0].height, datasets[0].classes) != (
            datasets[1].channels,
            datasets[1].height,
            datasets[1].classes,
        ):
            raise SemanticError(
                training_node, "DATASET_MISMATCH", "训练与测试数据的输入格式和类别数必须一致。"
            )
        channels = datasets[0].channels
        transforms: list[TransformDef] = []
        loaders: list[LoaderDef] = []
        dataset_index = {item.id: item for item in datasets}
        for node in used.values():
            fields = node.fields
            if node.type_id == "data.compose":
                children = node.inputs["steps"]
                if [n.type_id for n in children] not in (
                    ["data.to_tensor"],
                    ["data.to_tensor", "data.normalize"],
                ):
                    raise SemanticError(
                        node,
                        "TRANSFORM_ORDER_INVALID",
                        "预处理必须先转为张量，之后最多一个归一化步骤。",
                    )
                steps: list[TransformStep] = []
                for child in children:
                    if child.type_id == "data.to_tensor":
                        steps.append(TensorStep(origin=child.origin))
                    else:
                        mean, std = child.fields["MEAN"], child.fields["STD"]
                        mean = mean * channels if len(mean) == 1 else mean
                        std = std * channels if len(std) == 1 else std
                        if len(mean) != channels or len(std) != channels:
                            raise SemanticError(
                                child,
                                "NORMALIZE_CHANNEL_MISMATCH",
                                f"归一化参数需要{channels}个通道的数值。",
                            )
                        steps.append(NormalizeStep(origin=child.origin, mean=mean, std=std))
                transforms.append(
                    TransformDef(
                        id=node.origin.block_id,
                        origin=node.origin,
                        name=fields["NAME"],
                        steps=steps,
                    )
                )
            elif node.type_id == "data.dataloader":
                loaders.append(
                    LoaderDef(
                        id=node.origin.block_id,
                        name=fields["NAME"],
                        origin=node.origin,
                        dataset_id=fields["DATASET_REF"],
                        batch_size=fields["BATCH_SIZE"],
                        shuffle=fields["SHUFFLE"],
                        role=dataset_index[fields["DATASET_REF"]].split,
                    )
                )
        transforms.sort(key=lambda item: item.id)
        loaders.sort(key=lambda item: (item.role != "train", item.id))
        model_node = index[training_node.fields["MODEL_REF"]]
        if not model_node.inputs["body"]:
            raise SemanticError(model_node, "MODEL_EMPTY", "模型至少需要一层。")
        model = ModelDef(
            id=model_node.origin.block_id,
            name=model_node.fields["NAME"],
            origin=model_node.origin,
            layers=[lower_layer(node) for node in model_node.inputs["body"]],
        )
        f = training_node.fields
        training = TrainingSpec(
            origin=training_node.origin,
            model_id=f["MODEL_REF"],
            train_loader_id=f["TRAIN_LOADER_REF"],
            test_loader_id=f["TEST_LOADER_REF"],
            optimizer=f["OPTIMIZER"],
            criterion=f["CRITERION"],
            learning_rate=f["LEARNING_RATE"],
            epochs=f["EPOCHS"],
            before=[lower_figure(n, "before") for n in training_node.inputs["before"]],
            body=[lower_figure(n, "body") for n in training_node.inputs["body"]],
            after=[lower_figure(n, "after") for n in training_node.inputs["after"]],
        )
        trace, shape_errors = shape_check(model, datasets[0])
        if shape_errors:
            return None, shape_errors
        catalog = definitions()
        imports: set[str] = set()

        def collect(node: BlockIR) -> None:
            imports.update(catalog[node.type_id]["imports"])
            for chain in node.inputs.values():
                for child in chain:
                    collect(child)

        for node in used.values():
            collect(node)
        program = ProgramIR(
            seed=project.settings.seed,
            execution_mode=project.settings.execution_mode,
            symbols=sorted([s for s in symbols if s.id in used], key=lambda s: s.id),
            transforms=transforms,
            datasets=datasets,
            dataloaders=loaders,
            model=model,
            training=training,
            imports=sorted(imports),
            shape_trace=trace,
        )
        return program, []
    except SemanticError as error:
        return None, [error.diagnostic]
    except ValidationError:
        return None, [
            Diagnostic(
                code="IR_INVALID",
                message="参数无法转为受支持的训练配置。",
                origin=training_node.origin,
            )
        ]
