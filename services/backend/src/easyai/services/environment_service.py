"""Read-only environment discovery/probe; only a verified authenticated transport.

No public execution API is registered until an authenticated connection manager
can provide the scope guard. Test transports are confined to the test suite.
"""

from contextlib import contextmanager
from dataclasses import dataclass, field
import json
import math
import threading
import time
from typing import Any, Callable, Iterator, Literal
from uuid import uuid4

from easyai.domain.catalog import RUNTIME_ROOT
from easyai.domain.environment import (
    EnvironmentCatalog,
    EnvironmentDescriptor,
    EnvironmentDiscoveryRequest,
    EnvironmentProbeReport,
    EnvironmentProbeRequest,
    EnvironmentProbeResult,
    EnvironmentRequest,
    EnvironmentScope,
    ProbeIssue,
    remote_path,
)
from easyai.security.files import read_regular
from easyai.services.environment_transport import (
    MAX_STDERR,
    MAX_STDOUT,
    CommandResult,
    EnvironmentFailure,
    ProbeTransport,
    ReadOnlyCommand,
)

DISCOVER_CONDA = (
    "command -v conda || :; "
    'for p in "$HOME/miniconda3/bin/conda" "$HOME/anaconda3/bin/conda" /opt/conda/bin/conda; '
    'do if [ -f "$p" ] && [ -x "$p" ]; then printf "%s\\n" "$p"; fi; done'
)


def _json(raw: bytes) -> dict[str, Any]:
    def pairs(values: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in values:
            if key in result:
                raise ValueError("Duplicate key")
            result[key] = value
        return result

    def invalid(_value: str) -> None:
        raise ValueError("Non-finite value")

    try:
        if len(raw) > MAX_STDOUT:
            raise ValueError("Output limit")
        value = json.loads(raw.decode("utf-8"), object_pairs_hook=pairs, parse_constant=invalid)
        if not isinstance(value, dict):
            raise ValueError("Expected JSON object")
        return value
    except (ValueError, UnicodeError, RecursionError):
        raise EnvironmentFailure("ENVIRONMENT_OUTPUT_INVALID") from None


@dataclass
class _Operation:
    request_id: str
    deadline: float
    cancel: threading.Event = field(default_factory=threading.Event)
    running: bool = True


class EnvironmentService:
    def __init__(
        self,
        transport: ProbeTransport,
        mutex: threading.RLock,
        verify_scope: Callable[[EnvironmentScope], None],
        clock: Callable[[], float] = time.monotonic,
    ):
        self.scope = transport.scope
        self._transport = transport
        self._mutex = mutex
        self._verify_scope = verify_scope
        self._clock = clock
        self._closed = False
        self._active: _Operation | None = None
        self._retired: dict[str, float] = {}
        self._environments: dict[str, EnvironmentDescriptor] = {}
        self._catalog_expires = 0.0
        self._conda: str | None = None
        self._ready: tuple[EnvironmentProbeResult, str | None, float] | None = None

    def _request_scope(self, request: EnvironmentRequest) -> None:
        if (
            request.project_id != self.scope.project_id
            or request.connection_id != self.scope.connection_id
        ):
            raise EnvironmentFailure("ENVIRONMENT_SCOPE_INVALID")

    def _guard(self, operation: _Operation) -> None:
        if self._closed or operation.cancel.is_set() or self._active is not operation:
            raise EnvironmentFailure("ENVIRONMENT_CANCELLED")
        if self._transport.scope != self.scope:
            raise EnvironmentFailure("ENVIRONMENT_TARGET_CHANGED")
        try:
            self._verify_scope(self.scope)
        except Exception:
            raise EnvironmentFailure("ENVIRONMENT_TARGET_CHANGED") from None
        if self._clock() >= operation.deadline:
            raise EnvironmentFailure("ENVIRONMENT_TIMEOUT")

    def _retire(self, request_id: str) -> None:
        now = self._clock()
        self._retired = {key: expiry for key, expiry in self._retired.items() if expiry > now}
        if request_id not in self._retired and len(self._retired) >= 64:
            raise EnvironmentFailure("ENVIRONMENT_REQUEST_LIMIT")
        self._retired[request_id] = now + 600

    @property
    def quiescent(self) -> bool:
        with self._mutex:
            return (self._active is None or not self._active.running) and self._transport.quiescent

    def authority(
        self, request: EnvironmentRequest, probe_id: str
    ) -> tuple[EnvironmentProbeResult, str | None, int]:
        with self._mutex:
            self._request_scope(request)
            self._verify_scope(self.scope)
            if self._closed or self._ready is None or self._clock() >= self._ready[2]:
                raise EnvironmentFailure("ENVIRONMENT_AUTHORITY_EXPIRED")
            value, conda, _expiry = self._ready
            if value.request_id != probe_id or value.scope != self.scope:
                raise EnvironmentFailure("ENVIRONMENT_AUTHORITY_INVALID")
            return (
                value.model_copy(deep=True),
                conda,
                max(1, min(120, math.floor(_expiry - self._clock()))),
            )

    def cancel_running(self, request: EnvironmentRequest) -> bool:
        with self._mutex:
            self._request_scope(request)
            running = (
                self._active is not None
                and self._active.running
                and self._active.request_id == request.request_id
            )
            self.cancel(request)
            return running

    def invalidate(self) -> None:
        with self._mutex:
            self._closed = True
            if self._active:
                self._active.cancel.set()
            self._environments.clear()
            self._ready = None
        try:
            self._transport.close()
        except Exception:
            pass

    def cancel(self, request: EnvironmentRequest) -> None:
        with self._mutex:
            self._request_scope(request)
            if self._active and self._active.request_id == request.request_id:
                self._active.cancel.set()
            self._retire(request.request_id)

    @contextmanager
    def _operation(self, request: EnvironmentRequest) -> Iterator[_Operation]:
        with self._mutex:
            self._request_scope(request)
            if self._closed:
                raise EnvironmentFailure("ENVIRONMENT_SESSION_CLOSED")
            if self._active and self._active.running:
                raise EnvironmentFailure("ENVIRONMENT_BUSY")
            self._retired = {
                key: expiry for key, expiry in self._retired.items() if expiry > self._clock()
            }
            if request.request_id in self._retired:
                raise EnvironmentFailure("ENVIRONMENT_REQUEST_RETIRED")
            self._retire(request.request_id)
            self._ready = None
            operation = _Operation(request.request_id, self._clock() + 20)
            self._active = operation
        try:
            with self._mutex:
                self._guard(operation)
            yield operation
        except Exception as error:
            self.invalidate()
            if isinstance(error, EnvironmentFailure):
                raise
            raise EnvironmentFailure("ENVIRONMENT_OPERATION_FAILED") from None
        finally:
            with self._mutex:
                operation.running = False

    def _execute(
        self, operation: _Operation, argv: tuple[str, ...], stdin: bytes = b"", seconds: float = 5
    ) -> CommandResult:
        with self._mutex:
            self._guard(operation)
            # Reserve the transport's 3s setup/drain margin and 2s close/join.
            budget = min(seconds, operation.deadline - self._clock() - 5)
            if budget <= 0:
                raise EnvironmentFailure("ENVIRONMENT_TIMEOUT")
        result = self._transport.execute(ReadOnlyCommand(argv, stdin, budget), operation.cancel)
        with self._mutex:
            self._guard(operation)
        if len(result.stdout) > MAX_STDOUT or len(result.stderr) > MAX_STDERR:
            raise EnvironmentFailure("ENVIRONMENT_OUTPUT_LIMIT")
        if type(result.exit_code) is not int or not 0 <= result.exit_code <= 255:
            raise EnvironmentFailure("ENVIRONMENT_EXIT_UNCONFIRMED")
        if result.exit_code in {124, 137}:
            raise EnvironmentFailure("ENVIRONMENT_TIMEOUT")
        if result.exit_code != 0:
            raise EnvironmentFailure("ENVIRONMENT_COMMAND_FAILED")
        return result

    def discover(self, request: EnvironmentDiscoveryRequest) -> EnvironmentCatalog:
        with self._operation(request) as operation:
            with self._mutex:
                self._environments.clear()
                self._catalog_expires = 0
                self._conda = None
            conda, version = request.conda_path, None
            locations: list[tuple[Literal["conda", "python"], str]] = []
            if request.python_path is not None:
                locations.append(("python", request.python_path))
            else:
                if conda is None:
                    raw = self._execute(operation, ("/bin/sh", "-c", DISCOVER_CONDA)).stdout
                    try:
                        paths = raw.decode("utf-8").splitlines()
                        if len(paths) > 4:
                            raise ValueError("Candidate limit")
                        candidates = [remote_path(path) for path in paths]
                    except (ValueError, UnicodeError):
                        raise EnvironmentFailure("ENVIRONMENT_DISCOVERY_INVALID") from None
                    conda = candidates[0] if candidates else None
                if conda is not None:
                    info = _json(self._execute(operation, (conda, "info", "--json")).stdout)
                    envs = _json(self._execute(operation, (conda, "env", "list", "--json")).stdout)
                    try:
                        base, version, prefixes = (
                            info["root_prefix"],
                            info["conda_version"],
                            envs["envs"],
                        )
                        if (
                            not isinstance(base, str)
                            or not isinstance(version, str)
                            or not 1 <= len(version) <= 128
                            or not isinstance(prefixes, list)
                            or len(prefixes) > 64
                            or not all(isinstance(prefix, str) for prefix in prefixes)
                        ):
                            raise ValueError("Invalid conda metadata")
                        remote_path(base)
                        if base not in prefixes or len(set(prefixes)) != len(prefixes):
                            raise ValueError("Invalid environment list")
                        locations = [("conda", remote_path(prefix)) for prefix in prefixes]
                    except (KeyError, TypeError, ValueError):
                        raise EnvironmentFailure("ENVIRONMENT_CONDA_INVALID") from None
            entries = [
                EnvironmentDescriptor(environment_id=str(uuid4()), kind=kind, location=path)
                for kind, path in locations
            ]
            with self._mutex:
                self._guard(operation)
                self._environments = {item.environment_id: item for item in entries}
                self._conda = conda
                self._catalog_expires = self._clock() + 600
                return EnvironmentCatalog(
                    **request.model_dump(include={"project_id", "connection_id", "request_id"}),
                    scope=self.scope,
                    environments=entries,
                    conda_executable=conda,
                    conda_version=version,
                    note="unprobed" if entries else "conda_not_found",
                )

    def probe(self, request: EnvironmentProbeRequest) -> EnvironmentProbeResult:
        with self._operation(request) as operation:
            with self._mutex:
                descriptor = self._environments.get(request.environment_id)
                if descriptor is None or self._catalog_expires <= self._clock():
                    raise EnvironmentFailure("ENVIRONMENT_SELECTION_STALE")
                conda = self._conda
            from easyai.compiler.bundle import runtime_sources

            source = (
                runtime_sources()["code/dataset_inputs.py"]
                + "\n"
                + read_regular(RUNTIME_ROOT / "probe.py", 24000).decode("utf-8")
            )
            argv: tuple[str, ...] = (descriptor.location, "-I", "-B", "-c", source)
            if descriptor.kind == "conda":
                if conda is None:
                    raise EnvironmentFailure("ENVIRONMENT_SELECTION_STALE")
                argv = (
                    conda,
                    "run",
                    "-p",
                    descriptor.location,
                    "--no-capture-output",
                    "python",
                    "-I",
                    "-B",
                    "-c",
                    source,
                )
            config = {
                "nonce": request.request_id,
                "device": request.device,
                "dataset": request.dataset.model_dump(by_alias=True) if request.dataset else None,
            }
            result = self._execute(
                operation, argv, json.dumps(config, allow_nan=False).encode(), seconds=12
            )
            try:
                report = EnvironmentProbeReport.model_validate(_json(result.stdout))
                if (
                    report.nonce != request.request_id
                    or report.tensor.device != request.device
                    or (request.dataset is None) != (report.dataset is None)
                ):
                    raise ValueError("Mismatched probe")
                if (
                    request.dataset
                    and report.dataset
                    and (
                        request.dataset.name != report.dataset.name
                        or request.dataset.data_root != report.dataset.data_root
                    )
                ):
                    raise ValueError("Mismatched data binding")
                if descriptor.kind == "conda" and report.python.prefix != descriptor.location:
                    raise ValueError("Mismatched selected prefix")
                if descriptor.kind == "python" and report.python.executable != descriptor.location:
                    raise ValueError("Mismatched selected interpreter")
            except (ValueError, TypeError):
                raise EnvironmentFailure("ENVIRONMENT_REPORT_INVALID") from None
            issues: list[ProbeIssue] = []
            if report.python.version[:2] != [3, 11]:
                issues.append(
                    ProbeIssue(
                        code="PYTHON_UNSUPPORTED",
                        suggestion="本版本已验证Python 3.11；请选择兼容的已有环境，不自动修改共享环境。",
                    )
                )
            import_codes: tuple[
                tuple[
                    str,
                    Literal[
                        "TORCH_IMPORT_FAILED",
                        "TORCHVISION_IMPORT_FAILED",
                        "MATPLOTLIB_IMPORT_FAILED",
                    ],
                ],
                ...,
            ] = (
                ("torch", "TORCH_IMPORT_FAILED"),
                ("torchvision", "TORCHVISION_IMPORT_FAILED"),
                ("matplotlib", "MATPLOTLIB_IMPORT_FAILED"),
            )
            for name, code in import_codes:
                if not getattr(report.imports, name).imported:
                    issues.append(
                        ProbeIssue(
                            code=code,
                            suggestion="请选择可实际导入兼容依赖的已有环境；探测不会安装或升级包。",
                        )
                    )
            if not report.tensor.ok:
                issues.append(
                    ProbeIssue(
                        code="TENSOR_CHECK_FAILED",
                        suggestion="检查所选设备和依赖；CPU或教师已有GPU环境需实际小张量检查通过。",
                    )
                )
            if report.dataset is not None and not report.dataset.ok:
                issues.append(
                    ProbeIssue(
                        code="DATASET_CHECK_FAILED",
                        suggestion="请检查教师预置数据格式与读取权限；download=False，不自动下载数据。",
                    )
                )
            with self._mutex:
                self._guard(operation)
                ready = (
                    report.python.version[:2] == [3, 11]
                    and all(
                        item.imported
                        for item in (
                            report.imports.torch,
                            report.imports.torchvision,
                            report.imports.matplotlib,
                        )
                    )
                    and report.tensor.ok
                )
                value = EnvironmentProbeResult(
                    project_id=request.project_id,
                    connection_id=request.connection_id,
                    request_id=request.request_id,
                    scope=self.scope,
                    environment_id=descriptor.environment_id,
                    report=report,
                    environment_ready=ready,
                    data_ready=report.dataset.ok if report.dataset else None,
                    issues=issues,
                )
                if ready and value.data_ready is True:
                    self._ready = (
                        value.model_copy(deep=True),
                        self._conda if descriptor.kind == "conda" else None,
                        self._clock() + 120,
                    )
                return value
