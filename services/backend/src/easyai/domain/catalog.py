import json
import sys
from pathlib import Path
from typing import Any

# Packaged builds copy this immutable resource next to easyai (M8 packaging).
SOURCE_ROOT = Path(__file__).resolve().parents[5]
CATALOG_PATH = (
    Path(getattr(sys, "_MEIPASS")) / "easyai/resources/manifest.json"
    if getattr(sys, "frozen", False)
    else SOURCE_ROOT / "packages/block-library/manifest.json"
)
RUNTIME_ROOT = (
    Path(getattr(sys, "_MEIPASS")) / "easyai/resources/runtime"
    if getattr(sys, "frozen", False)
    else SOURCE_ROOT / "runtime"
)
TEMPLATE_PATH = (
    Path(getattr(sys, "_MEIPASS")) / "easyai/resources/templates/project.easyai.json"
    if getattr(sys, "frozen", False)
    else SOURCE_ROOT / "examples/mnist-cnn/project.easyai.json"
)


def load_catalog() -> dict[str, Any]:
    value: dict[str, Any] = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
    return value


def definitions() -> dict[str, dict[str, Any]]:
    return {block["id"]: block for block in load_catalog()["blocks"]}


# Explicit trusted targets; M2 adds emitters, never imports project-supplied code.
HANDLER_IDS = frozenset(
    {
        "data.compose",
        "data.to_tensor",
        "data.normalize",
        "data.dataset_builtin",
        "data.dataloader",
        "model.define",
        "model.sequential",
        "model.conv2d",
        "model.linear",
        "model.relu",
        "model.maxpool2d",
        "model.dropout",
        "model.flatten",
        "train.loop",
        "viz.figure",
        "viz.panel",
        "viz.data_source",
        "viz.title",
        "viz.legend",
        "viz.axis",
        "viz.savefig",
    }
)
