"""Fixed, stdlib-bootstrapped environment probe. Never installs/downloads/trains.

Executed by a selected Python using -I -B -c with this immutable source and a
bounded JSON configuration on stdin; no remote script staging is necessary.
"""

import contextlib
import importlib
import importlib.metadata
import json
import os
import re
from pathlib import PurePosixPath
import sys
import tempfile
from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    # Production prepends this exact shared stdlib source to the fixed -c payload.
    from easyai.runtime.dataset_inputs import construct_dataset


def _path(value: Any) -> str:
    if (
        not isinstance(value, str)
        or not value.startswith("/")
        or value == "/"
        or len(value) > 1024
        or ".." in PurePosixPath(value).parts
        or "\\" in value
        or any(ord(char) < 32 or ord(char) == 127 for char in value)
    ):
        raise ValueError("ENVIRONMENT_CONFIG_INVALID")
    return value


def _config(raw: bytes) -> dict[str, Any]:
    def pairs(values: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in values:
            if key in result:
                raise ValueError("ENVIRONMENT_CONFIG_INVALID")
            result[key] = value
        return result

    value = json.loads(raw.decode("utf-8"), object_pairs_hook=pairs)
    if (
        len(raw) > 8192
        or not isinstance(value, dict)
        or set(value) != {"nonce", "device", "dataset"}
        or not isinstance(value["nonce"], str)
        or not re.fullmatch(
            r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}",
            value["nonce"],
        )
        or value["device"] not in ("cpu", "cuda", "mps")
    ):
        raise ValueError("ENVIRONMENT_CONFIG_INVALID")
    dataset = value["dataset"]
    if dataset is not None:
        if (
            not isinstance(dataset, dict)
            or set(dataset) != {"name", "dataRoot"}
            or dataset["name"] not in ("MNIST", "FashionMNIST", "CIFAR10")
        ):
            raise ValueError("ENVIRONMENT_CONFIG_INVALID")
        _path(dataset["dataRoot"])
    return value


def _package(name: str) -> tuple[dict[str, Any], Any]:
    version = None
    try:
        version = importlib.metadata.version(name)
    except Exception:
        pass
    try:
        module = importlib.import_module(name)
        return {"version": version, "imported": True, "error": None}, module
    except ModuleNotFoundError as error:
        code = "missing" if error.name == name else "import_failed"
        return {"version": version, "imported": False, "error": code}, None
    except Exception:
        return {"version": version, "imported": False, "error": "import_failed"}, None


def inspect_environment(config: dict[str, Any]) -> dict[str, Any]:
    imports: dict[str, Any] = {}
    modules: dict[str, Any] = {}
    for name in ("torch", "torchvision", "matplotlib"):
        imports[name], modules[name] = _package(name)
    torch = modules["torch"]
    devices: dict[str, bool | None] = {"cudaAvailable": None, "mpsAvailable": None}
    tensor: dict[str, Any] = {
        "attempted": False,
        "ok": False,
        "device": config["device"],
        "error": "dependency_missing",
    }
    if torch is not None:
        for name, query in (
            ("cudaAvailable", lambda: torch.cuda.is_available()),
            ("mpsAvailable", lambda: torch.backends.mps.is_available()),
        ):
            try:
                devices[name] = bool(query())
            except Exception:
                devices[name] = None
        selected = config["device"]
        available = selected == "cpu" or devices.get(selected + "Available") is True
        tensor["error"] = "device_unavailable"
        if available:
            tensor["attempted"] = True
            try:
                torch.set_num_threads(1)
                with torch.no_grad():
                    sample = torch.ones((1, 1, 4, 4), device=selected)
                    layer = torch.nn.Conv2d(1, 1, 3, bias=False).to(selected)
                    output = layer(sample)
                    if (
                        list(output.shape) != [1, 1, 2, 2]
                        or not torch.isfinite(output).all().item()
                    ):
                        raise ValueError("Invalid convolution result")
                tensor.update(ok=True, error=None)
            except Exception:
                tensor["error"] = "execution_failed"
    dataset = None
    if config["dataset"] is not None:
        binding = config["dataset"]
        dataset = {
            "name": binding["name"],
            "dataRoot": binding["dataRoot"],
            "ok": False,
            "sampleShape": None,
            "sampleDtype": None,
            "label": None,
            "error": "dependency_missing",
        }
        vision = modules["torchvision"]
        if binding["name"] == "CIFAR10":
            # download=False still invokes pickle.load and full-data MD5 in the
            # official CIFAR adapter. Do not execute untrusted reducers during
            # a preflight. A safe construction boundary remains unimplemented.
            dataset["error"] = "unsafe_format_blocked"
        elif torch is not None and vision is not None:
            try:
                # Fixed whitelist, both required splits; no download or dataset writes.
                constructor = getattr(vision.datasets, binding["name"])
                for training_split in (True, False):
                    selected_data = construct_dataset(
                        constructor,
                        root=binding["dataRoot"],
                        train=training_split,
                        transform=vision.transforms.ToTensor(),
                        download=False,
                    )
                    if len(selected_data) < 1:
                        raise ValueError("Empty dataset")
                    sample, label = selected_data[0]
                    shape = list(sample.shape)
                    expected = [3, 32, 32] if binding["name"] == "CIFAR10" else [1, 28, 28]
                    if shape != expected or type(label) is not int or not 0 <= label <= 9:
                        raise ValueError("Invalid sample")
                dataset.update(
                    ok=True,
                    sampleShape=shape,
                    sampleDtype=str(sample.dtype),
                    label=label,
                    error=None,
                )
            except Exception:
                dataset["error"] = "unavailable"
    return {
        "schemaVersion": 1,
        "nonce": config["nonce"],
        "platform": sys.platform,
        "python": {
            "executable": sys.executable,
            "prefix": sys.prefix,
            "version": list(sys.version_info[:3]),
        },
        "imports": imports,
        "devices": devices,
        "tensor": tensor,
        "dataset": dataset,
    }


def main() -> None:
    try:
        config = _config(sys.stdin.buffer.read(8193))
        sys.dont_write_bytecode = True
        # Isolate third-party caches in this process's temporary directory;
        # no modification of the selected environment or teacher data directory.
        with tempfile.TemporaryDirectory(prefix="easyai-probe-") as cache:
            for name in (
                "MPLCONFIGDIR",
                "XDG_CACHE_HOME",
                "TORCH_HOME",
                "PYTORCH_KERNEL_CACHE_PATH",
                "CUDA_CACHE_PATH",
            ):
                os.environ[name] = cache
            os.environ["MPLBACKEND"] = "Agg"
            with contextlib.redirect_stdout(sys.stderr):
                report = inspect_environment(config)
            print(
                json.dumps(report, ensure_ascii=True, allow_nan=False, separators=(",", ":")),
                flush=True,
            )
    except Exception:
        print("ENVIRONMENT_PROBE_FAILED", file=sys.stderr, flush=True)
        raise SystemExit(2) from None


if __name__ == "__main__":
    main()
