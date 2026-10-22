"""Portable IDX-only selection for the two official MNIST adapters.

Importing this module never imports torch/torchvision or reads dataset contents.
"""

import ast
import importlib
import os
from pathlib import Path
import stat
from typing import Any

NAMES = frozenset({"MNIST", "FashionMNIST"})


def reject_legacy_cache(root: str | Path, name: str) -> None:
    if name not in NAMES:
        raise ValueError("DATASET_PREFLIGHT_NOT_SUPPORTED")
    root = Path(root)
    processed = root / name / "processed"
    for path in (root, root / name, processed):
        try:
            info = path.lstat()
        except FileNotFoundError:
            continue
        if not stat.S_ISDIR(info.st_mode):
            raise ValueError("DATA_PATH_FORBIDDEN")
    for file in ("training.pt", "test.pt"):
        if os.path.lexists(processed / file):
            raise ValueError("DATASET_LEGACY_CACHE_FORBIDDEN")


def require_guarded_code(code: str) -> None:
    """Old compiler outputs remain viewable, but cannot newly start/export."""
    for node in ast.walk(ast.parse(code)):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            if (
                isinstance(node.func.value, ast.Name)
                and node.func.value.id == "datasets"
                and node.func.attr in NAMES
            ):
                raise ValueError("DATASET_INPUT_GUARD_REQUIRED")


def _raw_folder(self: Any) -> str:
    return os.path.join(self.root, self._easyai_dataset_name, "raw")


def _processed_folder(self: Any) -> str:
    return os.path.join(self.root, self._easyai_dataset_name, "processed")


def _never_legacy(self: Any) -> bool:
    reject_legacy_cache(self.root, self._easyai_dataset_name)
    return False


def _block_legacy(self: Any) -> Any:
    raise ValueError("DATASET_LEGACY_CACHE_FORBIDDEN")


def _raw_type(name: str, base: type[Any]) -> type[Any]:
    key = "_Raw" + name
    existing = globals().get(key)
    if isinstance(existing, type) and existing.__bases__ == (base,):
        return existing
    result = type(
        key,
        (base,),
        {
            "__module__": __name__,
            "_easyai_dataset_name": name,
            "raw_folder": property(_raw_folder),
            "processed_folder": property(_processed_folder),
            "_check_legacy_exist": _never_legacy,
            "_load_legacy_data": _block_legacy,
        },
    )
    globals()[key] = result
    return result


def __getattr__(name: str) -> type[Any]:
    # Spawn workers can reconstruct module-level adapter types without putting
    # torchvision imports into the application/preflight process.
    dataset = name.removeprefix("_Raw")
    if name != "_Raw" + dataset or dataset not in NAMES:
        raise AttributeError(name)
    vision = importlib.import_module("torchvision")
    return _raw_type(dataset, getattr(vision.datasets, dataset))


def construct_dataset(
    constructor: type[Any],
    *,
    root: str,
    train: bool,
    transform: Any,
    download: bool = False,
) -> Any:
    name = constructor.__name__
    if name not in NAMES or download is not False:
        raise ValueError("DATASET_PREFLIGHT_NOT_SUPPORTED")
    reject_legacy_cache(root, name)
    return _raw_type(name, constructor)(root=root, train=train, transform=transform, download=False)
