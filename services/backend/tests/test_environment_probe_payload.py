"""Fixed probe source with synthetic modules only; no installed torch is imported."""

import contextlib
import builtins
import socket
import importlib.util
import io
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from easyai.domain.environment import EnvironmentProbeReport

ROOT = Path(__file__).resolve().parents[3]


@pytest.fixture(autouse=True)
def prohibit_real_imports_and_network(monkeypatch):
    original = builtins.__import__

    def guarded(name, *args, **kwargs):
        if name.split(".")[0] in {"torch", "torchvision", "matplotlib"}:
            pytest.fail("Payload suite must never import actual training packages")
        return original(name, *args, **kwargs)

    def no_socket(*args, **kwargs):
        pytest.fail("Payload suite cannot dial sockets")

    monkeypatch.setattr(builtins, "__import__", guarded)
    monkeypatch.setattr(socket, "create_connection", no_socket)


@pytest.fixture
def payload(monkeypatch):
    spec = importlib.util.spec_from_file_location(
        "easyai_synthetic_probe_payload", ROOT / "runtime/probe.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    monkeypatch.setattr(
        module,
        "sys",
        SimpleNamespace(
            executable="/synthetic/python",
            prefix="/synthetic/base",
            version_info=(3, 11, 0),
            platform="linux",
        ),
    )
    return module


def config(dataset=None):
    return {"nonce": "11111111-1111-4111-8111-111111111111", "device": "cpu", "dataset": dataset}


@pytest.mark.parametrize("missing_train", [False, True])
@pytest.mark.parametrize("name", ["MNIST", "FashionMNIST", "CIFAR10"])
def test_fixed_payload_executes_small_conv_and_exact_offline_dataset_call_with_synthetic_modules(
    payload, monkeypatch, name, missing_train
):
    calls = []

    class Layer:
        def to(self, device):
            calls.append(("layer-device", device))
            return self

        def __call__(self, sample):
            calls.append(("conv-executed", sample))
            return SimpleNamespace(shape=(1, 1, 2, 2))

    def conv(*args, **kwargs):
        calls.append(("conv-created", args, kwargs))
        return Layer()

    torch = SimpleNamespace(
        cuda=SimpleNamespace(is_available=lambda: False),
        backends=SimpleNamespace(mps=SimpleNamespace(is_available=lambda: False)),
        set_num_threads=lambda count: calls.append(("threads", count)),
        no_grad=contextlib.nullcontext,
        ones=lambda shape, device: (shape, device),
        nn=SimpleNamespace(Conv2d=conv),
        isfinite=lambda _: SimpleNamespace(all=lambda: SimpleNamespace(item=lambda: True)),
    )
    shape = (3, 32, 32) if name == "CIFAR10" else (1, 28, 28)

    class Dataset:
        def __len__(self):
            return 1

        def __getitem__(self, index):
            assert index == 0
            return SimpleNamespace(shape=shape, dtype="synthetic.float32"), 2

    def constructor(**kwargs):
        calls.append(("dataset", kwargs))
        if missing_train and kwargs["train"]:
            raise RuntimeError("synthetic missing training split")
        return Dataset()

    vision = SimpleNamespace(
        datasets=SimpleNamespace(**{name: constructor}),
        transforms=SimpleNamespace(ToTensor=lambda: "synthetic-transform"),
    )
    modules = {"torch": torch, "torchvision": vision, "matplotlib": SimpleNamespace()}

    def package(package_name):
        return {"version": "synthetic-only", "imported": True, "error": None}, modules[package_name]

    monkeypatch.setattr(payload, "_package", package)
    report = EnvironmentProbeReport.model_validate(
        payload.inspect_environment(config({"name": name, "dataRoot": "/remote/teacher data"}))
    )
    assert report.tensor.ok
    if name == "CIFAR10":
        assert not report.dataset.ok
        assert report.dataset.error == "unsafe_format_blocked"
        assert report.dataset.sample_shape is None and report.dataset.label is None
        assert not any(call[0] == "dataset" for call in calls)
        return
    if missing_train:
        assert not report.dataset.ok
        assert [call[1]["train"] for call in calls if call[0] == "dataset"] == [True]
        return
    assert report.dataset.ok
    assert ("conv-created", (1, 1, 3), {"bias": False}) in calls
    assert any(call[0] == "conv-executed" for call in calls)
    dataset_calls = [call[1] for call in calls if call[0] == "dataset"]
    assert dataset_calls == [
        {
            "root": "/remote/teacher data",
            "train": training,
            "transform": "synthetic-transform",
            "download": False,
        }
        for training in (True, False)
    ]


def test_missing_imports_keep_device_state_unknown_and_never_attempt_data_or_tensor(
    payload, monkeypatch
):
    seen = []

    def missing(name):
        seen.append(name)
        return {"version": None, "imported": False, "error": "missing"}, None

    monkeypatch.setattr(payload, "_package", missing)
    report = EnvironmentProbeReport.model_validate(
        payload.inspect_environment(config({"name": "MNIST", "dataRoot": "/remote/data"}))
    )
    assert seen == ["torch", "torchvision", "matplotlib"]
    assert report.devices.cuda_available is None and report.devices.mps_available is None
    assert not report.tensor.attempted and report.tensor.error == "dependency_missing"
    assert not report.dataset.ok and report.dataset.error == "dependency_missing"


def test_payload_main_uses_only_process_temporary_caches_including_cuda(
    payload, monkeypatch, tmp_path
):
    output = []
    environment = {"MPLCONFIGDIR": "/synthetic/teacher-original"}
    monkeypatch.setattr(payload, "os", SimpleNamespace(environ=environment))
    payload.sys.stdin = SimpleNamespace(buffer=io.BytesIO(json.dumps(config()).encode()))
    payload.sys.stderr = io.StringIO()

    @contextlib.contextmanager
    def temporary(**kwargs):
        yield str(tmp_path)

    monkeypatch.setattr(payload.tempfile, "TemporaryDirectory", temporary)

    def inspect(value):
        for name in (
            "MPLCONFIGDIR",
            "XDG_CACHE_HOME",
            "TORCH_HOME",
            "PYTORCH_KERNEL_CACHE_PATH",
            "CUDA_CACHE_PATH",
        ):
            assert environment[name] == str(tmp_path)
        assert environment["MPLBACKEND"] == "Agg"
        return {"synthetic": True, "nonce": value["nonce"]}

    monkeypatch.setattr(payload, "inspect_environment", inspect)
    monkeypatch.setattr(payload, "print", lambda text, **kwargs: output.append(text), raising=False)
    payload.main()
    assert json.loads(output[0]) == {"synthetic": True, "nonce": config()["nonce"]}
    assert payload.sys.dont_write_bytecode is True


@pytest.mark.parametrize("raw", [b'{"nonce":"x","nonce":"y"}', b"{}", b"x" * 8193])
def test_payload_rejects_invalid_bounded_stdin_before_imports(payload, monkeypatch, raw):
    monkeypatch.setattr(payload, "_package", lambda _: pytest.fail("Must not import packages"))
    with pytest.raises(ValueError):
        payload._config(raw)
