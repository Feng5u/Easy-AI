"""Reviewed offline selections, never a network resolver or executable package loader."""

import hashlib
import json
from pathlib import Path
from typing import TypedDict

from easyai.security.files import read_regular


class Wheel(TypedDict):
    name: str
    version: str
    filename: str
    url: str
    sha256: str
    downloadBytes: int
    unpackedBytes: int | None


ML_ROOTS = frozenset({"scipy", "pandas", "scikit-learn"})
IMPORTS = {
    "torch": "torch",
    "torchvision": "torchvision",
    "matplotlib": "matplotlib",
    "scipy": "scipy",
    "pandas": "pandas",
    "scikit-learn": "sklearn",
    "joblib": "joblib",
    "threadpoolctl": "threadpoolctl",
}
CORE_SOURCES = "easyai-cpu-sources.json"
CORE_LOCK = "easyai-cpu-linux-cp311.lock"
ML_SOURCES = "easyai-ml-sources.json"
ML_LOCK = "easyai-ml-linux-cp311.lock"
ML_HEADER = "# Optional ML wheels; CPython 3.11 / Linux x86_64; no extras. Requires core lock.\n"


def _pins(packages: list[Wheel]) -> bytes:
    return "".join(
        f"{w['name']}=={w['version']} \\\n    --hash=sha256:{w['sha256']}\n"
        for w in sorted(packages, key=lambda w: w["name"])
    ).encode()


def wheels(root: Path, selected: set[str] | None = None) -> list[Wheel]:
    base: list[Wheel] = json.loads(read_regular(root / CORE_SOURCES, 100000))["packages"]
    if not selected or not selected.intersection(ML_ROOTS):
        return base
    value = json.loads(read_regular(root / ML_SOURCES, 100000))
    extra: list[Wheel] = value["packages"]
    # Both reviewed files must agree before any plan or command consumes them.
    if read_regular(root / ML_LOCK, 100000) != ML_HEADER.encode() + _pins(extra):
        raise ValueError("INSTALL_DEPENDENCIES_UNRESOLVED")
    dependencies: dict[str, list[str]] = value["dependencies"]
    known = {w["name"] for w in base}
    pending = list(selected.intersection(ML_ROOTS))
    included: set[str] = set()
    while pending:
        name = pending.pop()
        if name in included or name in known:
            continue
        if name not in dependencies or not any(w["name"] == name for w in extra):
            raise ValueError("INSTALL_DEPENDENCIES_UNRESOLVED")
        included.add(name)
        pending.extend(dependencies[name])
    return base + [w for w in extra if w["name"] in included]


def constraints_hash(root: Path) -> str:
    return hashlib.sha256(
        b"".join(
            read_regular(root / name, 100000)
            for name in (CORE_SOURCES, CORE_LOCK, ML_SOURCES, ML_LOCK)
        )
    ).hexdigest()


def lock_bytes(root: Path, selected: set[str]) -> bytes:
    core = read_regular(root / CORE_LOCK, 100000)
    if not selected.intersection(ML_ROOTS):
        return core
    base = {w["name"] for w in wheels(root)}
    return core + b"\n" + _pins([w for w in wheels(root, selected) if w["name"] not in base])
