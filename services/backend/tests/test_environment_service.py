"""Synthetic protocol fixtures only: NO real packages, hardware, credentials or SSH."""

from concurrent.futures import ThreadPoolExecutor
import json
import socket
import threading
from uuid import uuid4

import pytest

from easyai.domain.environment import (
    DatasetProbe,
    EnvironmentDiscoveryRequest,
    EnvironmentProbeRequest,
    EnvironmentRequest,
    EnvironmentScope,
)
from easyai.domain.ssh import SshEndpoint
from easyai.services.environment_service import EnvironmentService
from easyai.services.environment_transport import CommandResult, EnvironmentFailure

PROJECT = "11111111-1111-4111-8111-111111111111"
CONNECTION = "22222222-2222-4222-8222-222222222222"


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("Synthetic environment suite cannot use network sockets")

    monkeypatch.setattr(socket, "create_connection", forbidden)


def request(kind=EnvironmentDiscoveryRequest, **kwargs):
    return kind(project_id=PROJECT, connection_id=CONNECTION, request_id=str(uuid4()), **kwargs)


def synthetic_report(config, executable="/synthetic/python", prefix="/synthetic/base"):
    package = {"version": "synthetic-fixture-only", "imported": True, "error": None}
    dataset = None
    if config["dataset"]:
        binding = config["dataset"]
        dataset = {
            **binding,
            "ok": True,
            "sampleShape": [3, 32, 32] if binding["name"] == "CIFAR10" else [1, 28, 28],
            "sampleDtype": "synthetic.dtype",
            "label": 0,
            "error": None,
        }
    return {
        "schemaVersion": 1,
        "nonce": config["nonce"],
        "platform": "linux",
        "python": {"executable": executable, "prefix": prefix, "version": [3, 11, 0]},
        "imports": {name: dict(package) for name in ("torch", "torchvision", "matplotlib")},
        "devices": {"cudaAvailable": None, "mpsAvailable": None},
        "tensor": {"attempted": True, "ok": True, "device": config["device"], "error": None},
        "dataset": dataset,
    }


class SyntheticTransport:
    def __init__(self):
        self.scope = EnvironmentScope(
            project_id=PROJECT,
            connection_id=CONNECTION,
            endpoint=SshEndpoint(host="synthetic.invalid"),
            host_fingerprint="SHA256:" + "A" * 43,
        )
        self.commands = []
        self.closed = False
        self.hook = None
        self.report_hook = None

    def close(self):
        self.closed = True

    def execute(self, command, cancel):
        self.commands.append(command)
        if self.hook:
            value = self.hook(command, cancel)
            if value is not None:
                return value
        argv = command.argv
        if argv[0] == "/bin/sh":
            raw = b"/synthetic/conda\n"
        elif argv[1:] == ("info", "--json"):
            raw = json.dumps(
                {
                    "root_prefix": "/synthetic/base",
                    "conda_version": "synthetic-only",
                    "extra_real_conda_field": [],
                }
            ).encode()
        elif argv[1:] == ("env", "list", "--json"):
            raw = b'{"envs":["/synthetic/base","/synthetic/class env"]}'
        else:
            config = json.loads(command.stdin)
            executable = argv[0] if "run" not in argv else "/synthetic/python"
            prefix = argv[argv.index("-p") + 1] if "run" in argv else "/synthetic/base"
            value = synthetic_report(config, executable, prefix)
            if self.report_hook:
                self.report_hook(value)
            raw = json.dumps(value).encode()
        return CommandResult(raw, b"", 0)


def setup():
    transport = SyntheticTransport()
    current = [transport.scope]
    clock = [1.0]

    def verify(scope):
        if scope != current[0]:
            raise ValueError("target changed")

    service = EnvironmentService(transport, threading.RLock(), verify, lambda: clock[0])
    return service, transport, current, clock


def test_fixed_conda_discovery_and_selected_prefix_command_are_read_only():
    service, transport, _, _ = setup()
    catalog = service.discover(request())
    assert catalog.scope == transport.scope and catalog.note == "unprobed"
    assert len(catalog.environments) == 2 and all(item.read_only for item in catalog.environments)
    descriptor = catalog.environments[1]
    result = service.probe(
        request(EnvironmentProbeRequest, environment_id=descriptor.environment_id)
    )
    assert result.environment_ready and result.data_ready is None
    argv = transport.commands[-1].argv
    assert argv[:9] == (
        "/synthetic/conda",
        "run",
        "-p",
        "/synthetic/class env",
        "--no-capture-output",
        "python",
        "-I",
        "-B",
        "-c",
    )
    assert "download=False" in argv[-1]
    assert all(
        "install" not in command.argv and "activate" not in command.argv
        for command in transport.commands
    )
    assert not transport.closed


@pytest.mark.parametrize("dataset", ["MNIST", "FashionMNIST", "CIFAR10"])
def test_explicit_python_and_remote_data_binding_are_exact(dataset):
    service, transport, _, _ = setup()
    catalog = service.discover(request(python_path="/synthetic/selected python"))
    assert transport.commands == []
    binding = DatasetProbe(name=dataset, data_root="/remote/teacher data")
    result = service.probe(
        request(
            EnvironmentProbeRequest,
            environment_id=catalog.environments[0].environment_id,
            dataset=binding,
        )
    )
    assert result.environment_ready and result.data_ready is True
    assert json.loads(transport.commands[-1].stdin)["dataset"] == {
        "name": dataset,
        "dataRoot": "/remote/teacher data",
    }


@pytest.mark.parametrize(
    "mutation",
    [
        "nonce",
        "device",
        "interpreter",
        "prefix",
        "dataset",
        "unknown_field",
        "false_import_tensor_success",
        "bool_version",
    ],
)
def test_bad_report_binding_or_shape_is_rejected_and_session_invalidated(mutation):
    service, transport, _, _ = setup()
    catalog = service.discover(
        request(conda_path="/synthetic/conda")
        if mutation == "prefix"
        else request(python_path="/synthetic/python")
    )

    def mutate(value):
        if mutation == "nonce":
            value["nonce"] = str(uuid4())
        elif mutation == "device":
            value["tensor"]["device"] = "cuda"
        elif mutation == "interpreter":
            value["python"]["executable"] = "/different/python"
        elif mutation == "prefix":
            value["python"]["prefix"] = "/different/prefix"
        elif mutation == "dataset":
            value["dataset"]["dataRoot"] = "/different/data"
        elif mutation == "unknown_field":
            value["arbitrary"] = "DO_NOT_LEAK_SYNTHETIC_MARKER"
        elif mutation == "false_import_tensor_success":
            value["imports"]["torch"].update(imported=False, error="missing")
        elif mutation == "bool_version":
            value["python"]["version"][0] = True

    transport.report_hook = mutate
    with pytest.raises(EnvironmentFailure, match="REPORT_INVALID") as raised:
        service.probe(
            request(
                EnvironmentProbeRequest,
                environment_id=catalog.environments[0].environment_id,
                dataset=DatasetProbe(name="MNIST", data_root="/remote/data"),
            )
        )
    assert transport.closed and not service._environments
    assert "DO_NOT_LEAK" not in str(raised.value)


@pytest.mark.parametrize(
    "raw",
    [
        b'{"envs":[],"envs":[]}',
        b"[]",
        b'{"envs":[NaN]}',
        b"prefix noise\n{}",
        b"\xff",
        b"{}" * 40000,
    ],
)
def test_bad_conda_output_is_never_plucked_from_noise(raw):
    service, transport, _, _ = setup()
    transport.hook = (
        lambda command, cancel: CommandResult(raw, b"", 0)
        if command.argv[1:] == ("env", "list", "--json")
        else None
    )
    with pytest.raises(EnvironmentFailure, match="(OUTPUT_INVALID|OUTPUT_LIMIT|CONDA_INVALID)"):
        service.discover(request(conda_path="/synthetic/conda"))
    assert transport.closed and not service._environments


def test_missing_conda_is_an_empty_unprobed_catalog_without_install():
    service, transport, _, _ = setup()
    transport.hook = lambda *_: CommandResult(b"", b"", 0)
    catalog = service.discover(request())
    assert catalog.environments == [] and catalog.note == "conda_not_found"
    assert len(transport.commands) == 1


def test_failures_provide_fixed_suggestions_and_never_invent_gpu_or_download_data():
    service, transport, _, _ = setup()
    catalog = service.discover(request(python_path="/synthetic/python"))

    def failed(value):
        for package in value["imports"].values():
            package.update(imported=False, error="import_failed")
        value["tensor"].update(attempted=False, ok=False, error="dependency_missing")
        value["dataset"].update(
            ok=False, sampleShape=None, sampleDtype=None, label=None, error="dependency_missing"
        )

    transport.report_hook = failed
    result = service.probe(
        request(
            EnvironmentProbeRequest,
            environment_id=catalog.environments[0].environment_id,
            dataset=DatasetProbe(name="CIFAR10", data_root="/remote/data"),
        )
    )
    assert not result.environment_ready and result.data_ready is False
    assert (
        result.report.devices.cuda_available is None and result.report.devices.mps_available is None
    )
    assert len(result.issues) == 5 and "download=False" in result.issues[-1].suggestion


def test_cancel_before_start_reuse_stale_catalog_and_wrong_scope_fail_before_execute():
    service, transport, _, _ = setup()
    pending = request()
    service.cancel(pending)
    with pytest.raises(EnvironmentFailure, match="RETIRED"):
        service.discover(pending)
    wrong = request().model_copy(update={"connection_id": str(uuid4())})
    with pytest.raises(EnvironmentFailure, match="SCOPE_INVALID"):
        service.discover(wrong)
    first = service.discover(request(python_path="/synthetic/python"))
    service.discover(request(python_path="/synthetic/other"))
    with pytest.raises(EnvironmentFailure, match="SELECTION_STALE"):
        service.probe(
            request(EnvironmentProbeRequest, environment_id=first.environments[0].environment_id)
        )
    assert transport.commands == [] and transport.closed


def test_late_result_after_cancel_target_switch_and_no_parallel_operation():
    for switch in (False, True):
        service, transport, current, _ = setup()
        entered, release = threading.Event(), threading.Event()
        req = request()

        def blocked(command, cancel):
            entered.set()
            assert release.wait(2)
            return CommandResult(b"", b"", 0)

        transport.hook = blocked
        with ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(service.discover, req)
            assert entered.wait(2)
            try:
                with pytest.raises(EnvironmentFailure, match="BUSY"):
                    service.discover(request())
                if switch:
                    current[0] = current[0].model_copy(update={"connection_id": str(uuid4())})
                else:
                    service.cancel(req)
            finally:
                release.set()
            with pytest.raises(EnvironmentFailure, match="(CANCELLED|TARGET_CHANGED)"):
                future.result(timeout=2)
        assert transport.closed and not service._environments


def test_total_budget_reserves_setup_and_cleanup_and_retention_is_bounded():
    service, transport, _, clock = setup()

    def advance(command, cancel):
        clock[0] += command.seconds + 3

    transport.hook = advance
    with pytest.raises(EnvironmentFailure, match="TIMEOUT"):
        service.discover(request())
    assert clock[0] <= 21  # started at 1; includes reserved transport margin.
    service, transport, _, clock = setup()
    for _ in range(64):
        service.cancel(request(EnvironmentRequest))
    with pytest.raises(EnvironmentFailure, match="REQUEST_LIMIT"):
        service.discover(request())
    assert len(service._retired) == 64 and transport.commands == []


@pytest.mark.parametrize("path", ["relative", "/", "/remote/../data", "/bad\npath", "/bad\\path"])
def test_invalid_remote_paths_and_free_command_fields_are_not_contracts(path):
    with pytest.raises(ValueError):
        request(python_path=path)
    with pytest.raises(ValueError):
        request(python_path="/synthetic/python", command="pip install something")
