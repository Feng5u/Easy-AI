import keyword
import re
from collections import Counter
from typing import Literal

from easyai.domain.contracts import BlockIR, Diagnostic, SymbolEntry

KINDS: dict[str, Literal["transform", "dataset", "dataloader", "model_class"]] = {
    "data.compose": "transform",
    "data.dataset_builtin": "dataset",
    "data.dataloader": "dataloader",
    "model.define": "model_class",
}
RESERVED = {
    "torch",
    "nn",
    "transforms",
    "datasets",
    "device",
    "model",
    "optimizer",
    "criterion",
    "main",
    "context",
    "self",
    "x",
    "y",
    "epoch",
    "train_loader",
    "test_loader",
    "random",
    "plt",
    "os",
    "sys",
    "json",
}


def registry(roots: list[BlockIR]) -> tuple[list[SymbolEntry], list[Diagnostic]]:
    definitions = {node.origin.block_id: node for node in roots if node.type_id in KINDS}
    entries: list[SymbolEntry] = []
    problems: list[Diagnostic] = []

    def report(node: BlockIR, code: str, message: str, field: str | None = None) -> None:
        problems.append(Diagnostic(code=code, message=message, origin=node.origin, field=field))

    def role(node: BlockIR, visiting: set[str]) -> Literal["train", "test"] | None:
        if node.origin.block_id in visiting:
            report(node, "REF_CYCLE", "对象引用形成了循环。")
            return None
        if node.type_id == "data.dataset_builtin":
            split = node.fields.get("SPLIT")
            return split if split in ("train", "test") else None
        if node.type_id == "data.dataloader":
            dep = definitions.get(node.fields.get("DATASET_REF", ""))
            if dep:
                return role(dep, visiting | {node.origin.block_id})
        return None

    for node in definitions.values():
        name = node.fields.get("NAME", "")
        registered = node.fields.get("REGISTERED", False)
        if (
            not re.fullmatch(r"[A-Za-z][A-Za-z0-9_]*", name)
            or keyword.iskeyword(name)
            or name in RESERVED
        ):
            report(node, "NAME_INVALID", "名称必须为非保留的英文 Python 名称。", "NAME")
        if node.origin.workspace == "training":
            report(node, "PLACEMENT_INVALID", "定义必须位于数据或模型工作区。")
            continue
        entries.append(
            SymbolEntry(
                id=node.origin.block_id,
                kind=KINDS[node.type_id],
                name=name,
                registered=registered,
                role=role(node, set()),
                workspace=node.origin.workspace,
            )
        )
    counts = Counter(entry.name for entry in entries)
    active = Counter((entry.kind, entry.role) for entry in entries if entry.registered)
    for entry in entries:
        node = definitions[entry.id]
        if counts[entry.name] > 1:
            report(node, "NAME_DUPLICATED", "项目中已有同名对象。", "NAME")
        if entry.registered and active[(entry.kind, entry.role)] > 1:
            report(node, "ROLE_DUPLICATED", "同类角色只能供项目引用一个对象。")
    index = {entry.id: entry for entry in entries}
    references: dict[str, list[tuple[str, str, str | None]]] = {
        "data.dataset_builtin": [("TRANSFORM_REF", "transform", None)],
        "data.dataloader": [("DATASET_REF", "dataset", None)],
        "train.loop": [
            ("MODEL_REF", "model_class", None),
            ("TRAIN_LOADER_REF", "dataloader", "train"),
            ("TEST_LOADER_REF", "dataloader", "test"),
        ],
    }
    training = [node for node in roots if node.type_id == "train.loop"]
    if len(training) != 1:
        problems.append(Diagnostic(code="TRAIN_ROOT_COUNT", message="需要一个活动训练管线。"))
    for node in roots:
        if node.type_id != "train.loop" and not node.fields.get("REGISTERED", False):
            continue
        for field, kind, expected_role in references.get(node.type_id, []):
            found = index.get(node.fields.get(field, ""))
            if found is None:
                report(node, "REF_NOT_FOUND", "找不到原先选择的对象。", field)
            elif not found.registered:
                report(node, "REF_NOT_REGISTERED", "选择的对象尚未供本项目引用。", field)
            elif found.kind != kind:
                report(node, "REF_TYPE_MISMATCH", "选择的对象类型不符。", field)
            elif expected_role and found.role != expected_role:
                report(node, "ROLE_MISMATCH", "训练与测试数据角色不符。", field)
        if (
            node.type_id == "data.dataloader"
            and role(node, set()) == "test"
            and node.fields.get("SHUFFLE") is not False
        ):
            report(node, "ROLE_MISMATCH", "测试数据不能打乱顺序。", "SHUFFLE")
        if node.type_id == "train.loop" and node.fields.get("CRITERION") != "CrossEntropy":
            report(node, "LOSS_NOT_SUPPORTED", "当前十分类任务仅支持交叉熵。", "CRITERION")
    return entries, problems
