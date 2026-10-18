"""Session-only Main-authorized selections; project/data paths never come from blocks."""

from contextlib import contextmanager
from dataclasses import dataclass
import json
import hashlib
import os
import struct
import subprocess
import threading
import signal
import time
from pathlib import Path
from typing import Any, Literal, BinaryIO, TYPE_CHECKING, Callable, Iterator, TypeVar
from uuid import uuid4

from easyai.compiler.pipeline import compile_project
from easyai.domain.catalog import TEMPLATE_PATH, BLANK_TEMPLATE_PATH
from easyai.domain.contracts import ProjectDocument, Run
from easyai.domain.connections import (
    SessionControl,
    AuthenticationRequest,
    ConnectionProfile,
    ConnectionProfileInput,
    ConnectionProfileUpdate,
)
from easyai.domain.ssh import SshEndpoint
from easyai.services.connection_profiles import ConnectionProfiles
from easyai.services.install_service import InstallService
from easyai.domain.remote_execution import (
    RemoteBinding,
    RemoteBindingRequest,
    RemoteRunStartRequest,
)
from easyai.domain.desktop import (
    ProjectSession,
    RunStartRequest,
    SelectionResult,
    LocalPreflightRequest,
    LocalPreflightResult,
    LocalPreflightCheck,
    LocalPythonVersions,
)
from easyai.security.files import read_regular
from easyai.services.project_service import ProjectService, read_project, validate_project_bytes
from easyai.services.run_service import RunService

T = TypeVar("T")


@dataclass(frozen=True)
class RunScope:
    run_id: str
    project_id: str
    generation: int


SelectionKind = Literal["project", "python", "data"]
if TYPE_CHECKING:
    from easyai.domain.ssh import IdentityRequest
    from easyai.services.connection_manager import ConnectionManager
    from easyai.services.ssh_identity import SshIdentityService
    from easyai.services.ssh_client import SshClient


def probe_python(python: Path, cache: Path) -> dict[str, Any]:
    """Only the explicitly selected executable runs this fixed import probe, never pip."""
    if cache.is_symlink():
        raise ValueError("LOCAL_STORAGE_FORBIDDEN")
    cache.mkdir(parents=True, exist_ok=True)
    environment = os.environ.copy()
    environment.update(PYTHONDONTWRITEBYTECODE="1", MPLCONFIGDIR=str(cache))
    script = (
        "import json,sys; import torch,torchvision,matplotlib; "
        "print('EASYAI_PROBE:'+json.dumps({'python':sys.executable,'prefix':sys.prefix,"
        "'torch':str(torch.__version__),'torchvision':str(torchvision.__version__),"
        "'matplotlib':str(matplotlib.__version__)}))"
    )
    try:
        process = subprocess.Popen(
            [str(python), "-I", "-B", "-c", script],
            env=environment,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            start_new_session=os.name == "posix",
        )
    except OSError:
        raise ValueError("ENVIRONMENT_PYTHON_UNAVAILABLE") from None
    buffers = [bytearray(), bytearray()]
    overflow = threading.Event()
    stopping = threading.Event()

    def drain(stream: BinaryIO, index: int) -> None:
        try:
            if os.name == "posix":
                # A descendant may retain a pipe after the selected leader exits.
                # Cancellable reads let cleanup retire both workers even if that
                # descendant escaped the owned group; never kill it by a bare PID.
                os.set_blocking(stream.fileno(), False)
            while not stopping.is_set():
                try:
                    chunk = os.read(stream.fileno(), 4096)
                except BlockingIOError:
                    stopping.wait(0.01)
                    continue
                if not chunk:
                    return
                if len(buffers[index]) + len(chunk) > 65536:
                    overflow.set()
                    return
                buffers[index].extend(chunk)
        except (OSError, ValueError):
            overflow.set()

    assert process.stdout is not None and process.stderr is not None
    threads = [
        threading.Thread(target=drain, args=(pipe, i), daemon=True, name=f"easyai-probe-drain-{i}")
        for i, pipe in enumerate((process.stdout, process.stderr))
    ]

    def kill_owned_group() -> None:
        # start_new_session above gives this probe its own POSIX group. Its
        # leader's exit does not imply its descendants or inherited pipes exited.
        if os.name == "posix":
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
        elif process.poll() is None:
            process.kill()

    deadline = time.monotonic() + 15
    timed_out = False
    cleanup_pending = False
    try:
        for thread in threads:
            thread.start()
        while process.poll() is None and not overflow.wait(0.01):
            if time.monotonic() >= deadline:
                timed_out = True
                break
        if overflow.is_set() or timed_out:
            kill_owned_group()
        try:
            process.wait(timeout=1)
        except subprocess.TimeoutExpired:
            timed_out = True
        drain_deadline = min(deadline, time.monotonic() + 0.25)
        for thread in threads:
            thread.join(max(0, drain_deadline - time.monotonic()))
        if any(thread.is_alive() for thread in threads):
            timed_out = True
    finally:
        # Always retire the group, including the leader-already-exited case.
        try:
            kill_owned_group()
            if process.poll() is None:
                try:
                    process.wait(timeout=1)
                except subprocess.TimeoutExpired:
                    cleanup_pending = True
        except OSError:
            cleanup_pending = True
        finally:
            cleanup_deadline = time.monotonic() + 1
            for thread in threads:
                if thread.ident is not None:
                    thread.join(max(0, cleanup_deadline - time.monotonic()))
            stopping.set()
            for thread in threads:
                if thread.ident is not None:
                    thread.join(0.1)
            process.stdout.close()
            process.stderr.close()
    if cleanup_pending or any(thread.is_alive() for thread in threads):
        raise ValueError("ENVIRONMENT_PROBE_CLEANUP_PENDING")
    if timed_out:
        raise ValueError("ENVIRONMENT_PROBE_TIMEOUT")
    if process.returncode != 0 or overflow.is_set():
        raise ValueError("ENVIRONMENT_IMPORT_FAILED")
    lines = [
        line.removeprefix(b"EASYAI_PROBE:")
        for line in bytes(buffers[0]).splitlines()
        if line.startswith(b"EASYAI_PROBE:")
    ]
    if len(lines) != 1:
        raise ValueError("ENVIRONMENT_PROBE_INVALID")
    try:
        value: Any = json.loads(lines[0])
    except (ValueError, UnicodeDecodeError):
        raise ValueError("ENVIRONMENT_PROBE_INVALID") from None
    if (
        not isinstance(value, dict)
        or set(value) != {"python", "prefix", "torch", "torchvision", "matplotlib"}
        or not all(isinstance(item, str) and item for item in value.values())
    ):
        raise ValueError("ENVIRONMENT_PROBE_INVALID")
    return value


def preflight_data(root: Path, dataset_names: set[str]) -> None:
    for dataset in dataset_names:
        if dataset not in {"MNIST", "FashionMNIST"}:
            raise ValueError("DATASET_PREFLIGHT_NOT_SUPPORTED")
        raw = root / dataset / "raw"
        current = root
        for part in (dataset, "raw"):
            current = current / part
            if current.is_symlink():
                raise ValueError("DATA_PATH_FORBIDDEN")
        for split in ("train", "t10k"):
            images = raw / f"{split}-images-idx3-ubyte"
            labels = raw / f"{split}-labels-idx1-ubyte"
            try:
                image_header = read_regular(images, 16, prefix=True)
                label_header = read_regular(labels, 8, prefix=True)
            except FileNotFoundError:
                raise ValueError("DATASET_MISSING_NO_DOWNLOAD") from None
            if len(image_header) != 16 or len(label_header) != 8:
                raise ValueError("DATASET_IDX_INVALID")
            magic, count, rows, columns = struct.unpack(">IIII", image_header)
            label_magic, labels_count = struct.unpack(">II", label_header)
            if (
                magic != 2051
                or label_magic != 2049
                or count <= 0
                or count != labels_count
                or (rows, columns) != (28, 28)
                or images.stat().st_size != 16 + count * rows * columns
                or labels.stat().st_size != 8 + count
            ):
                raise ValueError("DATASET_IDX_INVALID")


class LocalWorkspace:
    def __init__(self, root: Path):
        if not root.is_absolute() or root.is_symlink():
            raise ValueError("LOCAL_STORAGE_FORBIDDEN")
        root.mkdir(parents=True, exist_ok=True)
        self.root = root.resolve(strict=True)
        run_root = self.root / "runs"
        if run_root.is_symlink():
            raise ValueError("LOCAL_STORAGE_FORBIDDEN")
        run_root.mkdir(exist_ok=True)
        self.runs = RunService(run_root)
        self._mutex = threading.RLock()
        self._local_probe_lock = threading.Lock()
        self.profiles = ConnectionProfiles(self.root)
        self._selections: dict[str, tuple[SelectionKind, Path]] = {}
        self._projects: dict[str, ProjectService] = {}
        self._current: str | None = None
        self._project_generation = 0
        self._closed = False
        self._install_service: InstallService | None = None
        self._closing = False
        self._remote_bindings: dict[
            str, tuple[RemoteBinding, str, str | None, float, dict[str, Any]]
        ] = {}
        self._ssh_client: SshClient | None = None
        self._ssh_identity: SshIdentityService | None = None
        self._connections: ConnectionManager | None = None
        self._readonly: tuple[Path, bytes, ProjectSession] | None = None
        self._restore_error = False
        remembered = self.root / "last-project.json"
        if remembered.exists() or remembered.is_symlink():
            try:
                value = json.loads(read_regular(remembered, 8192))
                if not isinstance(value, dict) or set(value) != {"projectRoot"}:
                    raise ValueError("LOCAL_SESSION_INVALID")
                prior = Path(value["projectRoot"])
                if not prior.is_absolute() or prior.resolve(strict=True) != prior:
                    raise ValueError("LOCAL_SESSION_INVALID")
                self.open(self.select("project", prior).selection_id)
            except (OSError, ValueError, KeyError, TypeError):
                self._restore_error = True

    def _verify(self) -> None:
        if self._closed or self._closing:
            raise ValueError("LOCAL_WORKSPACE_CLOSED")

    def ssh(self) -> "SshClient":
        with self._mutex:
            self._verify()
            if self._ssh_client is None:
                from easyai.security.host_keys import HostKeyStore
                from easyai.services.ssh_client import SshClient

                self._ssh_client = SshClient(lambda: HostKeyStore(self.root / "ssh-host-identity"))
            return self._ssh_client

    def identity(self) -> "SshIdentityService":
        with self._mutex:
            self._verify()
            if self._ssh_identity is None:
                from easyai.services.ssh_identity import SshIdentityService

                self._ssh_identity = SshIdentityService(
                    self.ssh(),
                    self._mutex,
                    self._identity_project,
                    before_probe=self.begin_identity_probe,
                )
            return self._ssh_identity

    def connections(self) -> "ConnectionManager":
        with self._mutex:
            self._verify()
            if self._connections is None:
                from easyai.services.connection_manager import ConnectionManager

                self._connections = ConnectionManager(
                    self.ssh(),
                    self.identity(),
                    self._mutex,
                    self._identity_project,
                    verify_target=self.verify_connection_target,
                )
            return self._connections

    def list_connection_profiles(self) -> list[ConnectionProfile]:
        with self._mutex:
            self._verify()
            return self.profiles.list()

    def create_connection_profile(self, request: ConnectionProfileInput) -> ConnectionProfile:
        with self._mutex:
            self._verify()
            return self.profiles.create(request)

    def update_connection_profile(
        self, target_id: str, request: ConnectionProfileUpdate
    ) -> ConnectionProfile:
        with self._mutex:
            self._verify()

            def guard(old: ConnectionProfile) -> None:
                if any(
                    entry.run.config.target_id == old.target_id
                    and not self.runs.remote.settled(entry.run)
                    for entry in self.runs._ledger.entries.values()
                ):
                    raise ValueError("CONNECTION_PROFILE_ACTIVE_CONFLICT")

            # Revoke before possible publication: fsync failure can follow replace.
            return self.profiles.update(
                target_id, request, guard, lambda: self._invalidate_connection_target(target_id)
            )

    def _invalidate_connection_target(self, target_id: str) -> None:
        # Profile updates retire only capabilities for that target, never a new
        # unrelated session that became active while a client awaited the save.
        self._remote_bindings = {
            key: value
            for key, value in self._remote_bindings.items()
            if value[0].target_id != target_id
        }
        if self._connections is not None:
            self._connections.invalidate_target(target_id)

    def verify_connection_target(
        self, request: AuthenticationRequest, endpoint: SshEndpoint
    ) -> None:
        with self._mutex:
            self._verify()
            if request.target_id is None:
                return  # Legacy short-lived sessions can read old runs, never create new bindings.
            profile = next(
                (item for item in self.profiles.list() if item.target_id == request.target_id), None
            )
            if (
                profile is None
                or profile.revision != request.target_revision
                or profile.endpoint != endpoint
                or profile.username != request.username
            ):
                raise ValueError("SSH_TARGET_REFERENCE_STALE")

    def begin_identity_probe(self) -> None:
        with self._mutex:
            self._remote_bindings.clear()
            if self._connections is not None:
                self._connections.invalidate()

    def cancel_identity_connection(self, request: "IdentityRequest") -> None:
        with self._mutex:
            if self._connections is not None:
                self._connections.cancel_identity(request)

    def _identity_project(self, project_id: str) -> None:
        self._verify()
        if self._current != project_id or self._readonly is not None:
            raise ValueError("SSH_IDENTITY_PROJECT_CHANGED")

    def _invalidate_identity(self) -> None:
        self._remote_bindings.clear()
        if self._connections is not None:
            self._connections.invalidate()
        if self._ssh_identity is not None:
            self._ssh_identity.invalidate()

    def select(self, kind: SelectionKind, path: Path) -> SelectionResult:
        with self._mutex:
            self._verify()
            if kind not in {"project", "python", "data"} or not path.is_absolute():
                raise ValueError("LOCAL_SELECTION_INVALID")
            if kind == "python":
                selected = Path(os.path.normpath(str(path)))
                if not selected.is_file():
                    raise ValueError("LOCAL_SELECTION_INVALID")
            else:
                selected = path.resolve(strict=True)
                if kind == "project" and selected.is_file():
                    if selected.name != "project.easyai.json":
                        raise ValueError("LOCAL_SELECTION_INVALID")
                    selected = selected.parent
                if not selected.is_dir():
                    raise ValueError("LOCAL_SELECTION_INVALID")
            identity = str(uuid4())
            self._selections[identity] = (kind, selected)
            return SelectionResult(selection_id=identity, kind=kind, label=str(selected))

    def _selection(self, identity: str, kind: SelectionKind) -> Path:
        self._verify()
        stored = self._selections.get(identity)
        if stored is None:
            raise KeyError("LOCAL_SELECTION_NOT_FOUND")
        if stored[0] != kind:
            raise ValueError("LOCAL_SELECTION_KIND_MISMATCH")
        return stored[1]

    def _session(self, service: ProjectService) -> ProjectSession:
        opened = read_project(service.path)
        if opened.document is None:
            raise ValueError("PROJECT_FORMAT_UNSUPPORTED")
        return ProjectSession(
            project=opened.document,
            read_only=opened.read_only or not service.owned,
            reason=opened.reason or service.lock_reason,
        )

    def current(self) -> ProjectSession | None:
        with self._mutex:
            self._verify()
            if self._restore_error:
                raise ValueError("LOCAL_SESSION_RESTORE_FAILED")
            if self._readonly is not None:
                return self._readonly[2]
            return self._session(self._projects[self._current]) if self._current else None

    def _register(self, service: ProjectService) -> ProjectSession:
        self._project_generation += 1
        self._invalidate_identity()
        session = self._session(service)
        assert session.project is not None
        identity = session.project.project_id
        previous = self._projects.get(identity)
        if previous is not None and previous.root != service.root:
            service.close()
            raise ValueError("PROJECT_ID_CONFLICT")
        self._projects[identity] = service
        self._current = identity
        self._readonly = None
        self._remember(service.root)
        return session

    def open(self, selection_id: str) -> ProjectSession:
        with self._mutex:
            self._project_generation += 1
            self._invalidate_identity()
            root = self._selection(selection_id, "project")
            for service in self._projects.values():
                if service.root == root:
                    session = self._session(service)
                    assert session.project is not None
                    self._current = session.project.project_id
                    self._readonly = None
                    self._remember(root)
                    return session
            # Reject unsupported bytes before creating metadata or acquiring ownership.
            opened = read_project(root / "project.easyai.json")
            if opened.document is None:
                session = ProjectSession(
                    project=None,
                    read_only=True,
                    reason=opened.reason,
                    raw_text=opened.raw[:65536].decode("utf-8", errors="replace"),
                    label=root.name,
                )
                self._readonly = (root, opened.raw, session)
                self._current = None
                self._remember(root)
                return session
            service = ProjectService(root)
            try:
                return self._register(service)
            except BaseException:
                service.close()
                raise

    def _remember(self, root: Path) -> None:
        ProjectService.atomic_write(
            self.root / "last-project.json",
            json.dumps({"projectRoot": str(root)}, ensure_ascii=False).encode(),
        )
        self._restore_error = False

    @staticmethod
    def _create_file(path: Path, payload: bytes) -> None:
        # Exclusive publication: even a native save dialog cannot silently replace user files.
        if path.exists() or path.is_symlink():
            raise ValueError("PROJECT_EXPORT_TARGET_EXISTS")
        temp = path.with_name("easyai-export-" + str(uuid4()) + ".tmp")
        try:
            with temp.open("xb") as stream:
                stream.write(payload)
                stream.flush()
                os.fsync(stream.fileno())
            try:
                os.link(temp, path)
            except FileExistsError:
                raise ValueError("PROJECT_EXPORT_TARGET_EXISTS") from None
        finally:
            temp.unlink(missing_ok=True)

    def export_current(self, destination: Path, document: ProjectDocument | None = None) -> None:
        with self._mutex:
            self._verify()
            if not destination.is_absolute():
                raise ValueError("LOCAL_SELECTION_INVALID")
            if document is not None:
                if self._current is None or document.project_id != self._current:
                    raise ValueError("PROJECT_ID_CONFLICT")
                raw = (document.model_dump_json(by_alias=True, indent=2) + "\n").encode()
                validate_project_bytes(raw)
            elif self._readonly is not None:
                raw = self._readonly[1]
                if len(raw) > 5 * 1024 * 1024:
                    # read_project retains a bounded prefix for oversized input.
                    # It is evidence of rejection, never a complete export source.
                    raise ValueError("PROJECT_SIZE_LIMIT")
            elif self._current is not None:
                raw = read_regular(self._projects[self._current].path, 5 * 1024 * 1024)
            else:
                raise ValueError("PROJECT_NOT_OPEN")
            self._create_file(destination, raw)

    def import_project(self, source: Path, destination: Path) -> ProjectSession:
        with self._mutex:
            self._verify()
            if not source.is_absolute() or not destination.is_absolute():
                raise ValueError("LOCAL_SELECTION_INVALID")
            root = destination.resolve(strict=True)
            if not root.is_dir() or (root / "project.easyai.json").exists():
                raise ValueError("PROJECT_ALREADY_EXISTS")
            raw = read_regular(source, 5 * 1024 * 1024)
            try:
                document = validate_project_bytes(raw)
            except (ValueError, RecursionError):
                # Unsupported content stays byte-exact and read-only, never sent to Blockly.
                pass
            else:
                document = document.model_copy(update={"project_id": str(uuid4()), "revision": 1})
                raw = (document.model_dump_json(by_alias=True, indent=2) + "\n").encode()
                validate_project_bytes(raw)
            self._create_file(root / "project.easyai.json", raw)
            return self.open(self.select("project", root).selection_id)

    def history(self, project_id: str, offset: int = 0, limit: int = 25) -> list[Run]:
        with self._mutex:
            self._verify()
            self.project_generation(project_id)
            if not 0 <= offset or not 1 <= limit <= 50:
                raise ValueError("HISTORY_CURSOR_INVALID")
            identities = [
                entry.run.run_id
                for entry in reversed(list(self.runs._ledger.entries.values()))
                if entry.run.project_id == project_id
            ]
            return [self.runs.get(identity) for identity in identities[offset : offset + limit]]

    def create(
        self, selection_id: str, name: str, template_name: str = "mnist-cnn"
    ) -> ProjectSession:
        with self._mutex:
            root = self._selection(selection_id, "project")
            path = root / "project.easyai.json"
            if path.exists() or path.is_symlink():
                raise ValueError("PROJECT_ALREADY_EXISTS")
            data = root / "data"
            if data.is_symlink() or (data.exists() and not data.is_dir()):
                raise ValueError("DATA_PATH_FORBIDDEN")
            if template_name not in {"mnist-cnn", "blank"}:
                raise ValueError("PROJECT_TEMPLATE_INVALID")
            template = validate_project_bytes(
                read_regular(
                    TEMPLATE_PATH if template_name == "mnist-cnn" else BLANK_TEMPLATE_PATH,
                    5 * 1024 * 1024,
                )
            )
            value = template.model_dump(by_alias=True)
            value.update(projectId=str(uuid4()), name=name, revision=1)
            document = ProjectDocument.model_validate(value)
            payload = (document.model_dump_json(by_alias=True, indent=2) + "\n").encode()
            service = ProjectService(root)
            try:
                if not service.owned:
                    raise ValueError("PROJECT_READ_ONLY")
                data.mkdir(exist_ok=True)
                try:
                    descriptor = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
                except FileExistsError:
                    raise ValueError("PROJECT_ALREADY_EXISTS") from None
                with os.fdopen(descriptor, "wb") as stream:
                    stream.write(payload)
                    stream.flush()
                    os.fsync(stream.fileno())
                return self._register(service)
            except BaseException:
                service.close()
                raise

    def save(self, project_id: str, document: ProjectDocument, revision: int) -> ProjectSession:
        with self._mutex:
            self._verify()
            if document.project_id != project_id:
                raise ValueError("PROJECT_ID_CONFLICT")
            service = self._projects[project_id]
            service.save(document, revision)
            return self._session(service)

    def require_run(self, run_id: str) -> Run:
        with self._mutex:
            self._verify()
            entry = self.runs._ledger.entries.get(run_id)
            if entry is None or entry.run.project_id != self._current or self._readonly is not None:
                raise KeyError("RUN_NOT_IN_CURRENT_PROJECT")
            return entry.run.model_copy(deep=True)

    def project_generation(self, project_id: str) -> int:
        with self._mutex:
            self._verify()
            if project_id != self._current or self._readonly is not None:
                raise KeyError("PROJECT_NOT_CURRENT")
            return self._project_generation

    def verify_project_generation(self, project_id: str, generation: int) -> None:
        if self.project_generation(project_id) != generation:
            raise KeyError("PROJECT_SCOPE_RETIRED")

    def run_scope(self, run_id: str) -> RunScope:
        with self._mutex:
            run = self.require_run(run_id)
            return RunScope(run_id, run.project_id, self._project_generation)

    def verify_run_scope(self, scope: RunScope) -> None:
        with self._mutex:
            self.require_run(scope.run_id)
            if scope.generation != self._project_generation or scope.project_id != self._current:
                raise KeyError("RUN_SCOPE_RETIRED")

    @contextmanager
    def run_commit_scope(self, scope: RunScope) -> Iterator[None]:
        with self._mutex:
            self.verify_run_scope(scope)
            yield

    def read_run(self, scope: RunScope, action: Callable[..., T], *args: Any) -> T:
        self.verify_run_scope(scope)
        try:
            value = action(*args)  # No workspace lock while acquiring core/store locks.
        except BaseException:
            self.verify_run_scope(scope)  # Retired requests must not deliver old errors either.
            raise
        self.verify_run_scope(scope)
        return value

    def cancel_run(self, scope: RunScope) -> Run:
        run = self.require_run(scope.run_id)
        if run.config.runner == "ssh":
            # request_cancel takes core -> workspace, as does the coordinator guard.
            value = self.runs.remote.cancel(scope.run_id, lambda: self.run_commit_scope(scope))
        else:
            with self.run_commit_scope(scope):
                value = self.runs.cancel(scope.run_id)
        self.verify_run_scope(scope)
        return value

    def verify_preflight_scope(self, request: LocalPreflightRequest, generation: int) -> None:
        with self._mutex:
            self.verify_project_generation(request.project_id, generation)
            self._projects[request.project_id].snapshot(request.expected_revision)

    def preflight_local(self, request: LocalPreflightRequest) -> LocalPreflightResult:
        # Capture authorized identities under the workspace lock, but never hold it
        # across a selected executable. A result is informational, never a run grant.
        with self._mutex:
            generation = self.project_generation(request.project_id)
            project = self._projects[request.project_id]
            opened = project.snapshot(request.expected_revision)
            assert opened.document is not None
            python = self._selection(request.python_selection_id, "python")
            data = self._selection(request.data_selection_id, "data")
        if not self._local_probe_lock.acquire(blocking=False):
            raise ValueError("LOCAL_PREFLIGHT_BUSY")
        try:
            compilation = compile_project(opened.document)
            names: set[str] = (
                {item.dataset_name for item in compilation.program.datasets}
                if compilation.program is not None
                else set()
            )
            data_check = LocalPreflightCheck(ok=False, code="DATASET_PROJECT_NOT_RUNNABLE")
            if names:
                try:
                    preflight_data(data, names)
                    data_check = LocalPreflightCheck(ok=True, code="DATASET_READY")
                except (OSError, ValueError) as error:
                    code = str(error)
                    allowed = {
                        "DATASET_PREFLIGHT_NOT_SUPPORTED",
                        "DATA_PATH_FORBIDDEN",
                        "DATASET_MISSING_NO_DOWNLOAD",
                        "DATASET_IDX_INVALID",
                    }
                    data_check = LocalPreflightCheck(
                        ok=False, code=code if code in allowed else "DATASET_UNREADABLE"
                    )
            versions = None
            try:
                versions = LocalPythonVersions.model_validate(
                    probe_python(python, self.root / "probe-cache")
                )
                environment = LocalPreflightCheck(ok=True, code="ENVIRONMENT_READY")
            except (OSError, ValueError) as error:
                code = str(error)
                allowed = {
                    "ENVIRONMENT_PYTHON_UNAVAILABLE",
                    "ENVIRONMENT_IMPORT_FAILED",
                    "ENVIRONMENT_PROBE_TIMEOUT",
                    "ENVIRONMENT_PROBE_INVALID",
                    "ENVIRONMENT_PROBE_CLEANUP_PENDING",
                    "LOCAL_STORAGE_FORBIDDEN",
                }
                environment = LocalPreflightCheck(
                    ok=False, code=code if code in allowed else "ENVIRONMENT_PROBE_INVALID"
                )
            with self._mutex:
                self.verify_project_generation(request.project_id, generation)
                project.snapshot(request.expected_revision)
                return LocalPreflightResult(
                    **request.model_dump(),
                    environment=environment,
                    data=data_check,
                    versions=versions,
                    dataset_names=sorted(names),
                )
        finally:
            self._local_probe_lock.release()

    def bind_remote(self, project_id: str, request: RemoteBindingRequest) -> RemoteBinding:
        with self._mutex:
            self._identity_project(project_id)
            from easyai.security.remote_cache import require_local_cache

            require_local_cache()
            if request.project_id != project_id:
                raise ValueError("REMOTE_BINDING_PROJECT_INVALID")
            manager = self.connections()
            control = SessionControl(project_id=project_id, connection_id=request.connection_id)
            auth = manager.current(control)
            if auth is None:
                raise ValueError("REMOTE_AUTHENTICATION_REQUIRED")
            if auth.target_id is None:
                raise ValueError("SSH_TARGET_PROFILE_REQUIRED")
            self.verify_connection_target(
                AuthenticationRequest(
                    project_id=project_id,
                    request_id=auth.request_id,
                    identity_request_id=auth.identity_request_id,
                    expected_fingerprint=auth.scope.host_fingerprint,
                    username=auth.username,
                    target_id=auth.target_id,
                    target_revision=auth.target_revision,
                ),
                auth.scope.endpoint,
            )
            report, conda, remaining = manager.environments(request).authority(
                request, request.probe_request_id
            )
            opened = self._projects[project_id].snapshot(request.expected_revision)
            if opened.document is None:
                raise ValueError("PROJECT_READ_ONLY")
            compiled = compile_project(opened.document)
            if not compiled.result.runnable or compiled.program is None:
                raise ValueError("PROJECT_NOT_RUNNABLE")
            if compiled.result.program_hash != request.expected_program_hash:
                raise ValueError("PROGRAM_HASH_CONFLICT")
            dataset = report.report.dataset
            if (
                not report.environment_ready
                or report.data_ready is not True
                or dataset is None
                or not dataset.ok
            ):
                raise ValueError("REMOTE_DATA_NOT_VERIFIED")
            if {item.dataset_name for item in compiled.program.datasets} != {dataset.name}:
                raise ValueError("REMOTE_DATA_BINDING_MISMATCH")
            if report.scope != auth.scope:
                raise ValueError("REMOTE_BINDING_SCOPE_INVALID")
            root = request.run_base
            if any(part in ("", ".", "..") for part in root.split("/")[1:]):
                raise ValueError("REMOTE_RUN_BASE_INVALID")
            now = time.monotonic()
            self._remote_bindings = {
                key: item for key, item in self._remote_bindings.items() if item[3] > now
            }
            if len(self._remote_bindings) >= 64:
                raise ValueError("REMOTE_BINDING_LIMIT")
            binding = RemoteBinding(
                binding_id=str(uuid4()),
                project_id=project_id,
                connection_id=auth.scope.connection_id,
                target_id=auth.target_id,
                environment_id=report.environment_id,
                data_binding_id=str(uuid4()),
                project_revision=opened.document.revision,
                program_hash=compiled.result.program_hash,
                python_executable=report.report.python.executable,
                environment_prefix=report.report.python.prefix if conda else None,
                device=report.report.tensor.device,
                dataset_name=dataset.name,
                data_root=dataset.data_root,
                run_base=root,
                expires_in_seconds=min(remaining, auth.expires_in_seconds),
            )
            evidence = {
                "probe": report.model_dump(mode="json", by_alias=True),
                "condaExecutable": conda,
                "binding": binding.model_dump(mode="json", by_alias=True),
            }
            self._remote_bindings[binding.binding_id] = (
                binding,
                request.probe_request_id,
                conda,
                now + binding.expires_in_seconds,
                evidence,
            )
            return binding

    def _start_remote(self, project_id: str, request: RemoteRunStartRequest, key: str) -> Run:
        with self._mutex:
            self._identity_project(project_id)
            replay = self.runs.remote.replay(project_id, request, key)
            if replay is not None:
                return replay  # No grant renewal, authentication, network I/O or restart.
            stored = self._remote_bindings.get(request.binding_id)
            if stored is None or time.monotonic() >= stored[3]:
                raise ValueError("REMOTE_BINDING_EXPIRED")
            binding, probe_id, _conda, _expiry, evidence = stored
            if (
                binding.project_id != project_id
                or binding.project_revision != request.expected_revision
                or binding.program_hash != request.expected_program_hash
            ):
                raise ValueError("REMOTE_BINDING_SNAPSHOT_INVALID")
            manager = self.connections()
            control = SessionControl(project_id=project_id, connection_id=binding.connection_id)
            auth = manager.current(control)
            if auth is None:
                raise ValueError("REMOTE_AUTHENTICATION_REQUIRED")
            if auth.target_id is None or auth.target_id != binding.target_id:
                raise ValueError("SSH_TARGET_PROFILE_REQUIRED")
            self.verify_connection_target(
                AuthenticationRequest(
                    project_id=project_id,
                    request_id=auth.request_id,
                    identity_request_id=auth.identity_request_id,
                    expected_fingerprint=auth.scope.host_fingerprint,
                    username=auth.username,
                    target_id=auth.target_id,
                    target_revision=auth.target_revision,
                ),
                auth.scope.endpoint,
            )
            from easyai.domain.environment import EnvironmentRequest

            scope_request = EnvironmentRequest(
                project_id=project_id, connection_id=binding.connection_id, request_id=str(uuid4())
            )
            report, conda, _remaining = manager.environments(scope_request).authority(
                scope_request, probe_id
            )
            if (
                report.model_dump(mode="json", by_alias=True) != evidence["probe"]
                or conda != evidence["condaExecutable"]
            ):
                raise ValueError("REMOTE_BINDING_AUTHORITY_CHANGED")
            run = self.runs.remote.prepare(
                self._projects[project_id], request, key, binding, auth, evidence
            )
        return self.runs.remote.begin(run.run_id, manager, control, initial=True)

    def resume_remote(self, run_id: str, request: SessionControl) -> Run:
        with self._mutex:
            run = self.require_run(run_id)
            self._identity_project(request.project_id)
            if run.project_id != request.project_id or run.config.runner != "ssh":
                raise ValueError("REMOTE_RESUME_TARGET_INVALID")
            if self.runs.remote.settled(run) and run.sync_state == "complete":
                return run
            manager = self.connections()
        return self.runs.remote.begin(run_id, manager, request, initial=False)

    def start(
        self, project_id: str, request: RunStartRequest | RemoteRunStartRequest, key: str
    ) -> Run:
        if isinstance(request, RemoteRunStartRequest):
            return self._start_remote(project_id, request, key)
        with self._mutex:
            self._verify()
            project = self._projects[project_id]
            python = self._selection(request.python_selection_id, "python")
            data = self._selection(request.data_selection_id, "data")
            # A retry refers to the original saved snapshot even if the editor
            # has since advanced. RunService still verifies the complete binding
            # identity and rejects reuse of this key for a different request.
            key_hash = hashlib.sha256(key.encode()).hexdigest()
            if any(
                entry.idempotency_hash == key_hash for entry in self.runs._ledger.entries.values()
            ):
                existing = self.runs.prepare(
                    project,
                    request.expected_revision,
                    request.expected_program_hash,
                    key,
                    python,
                    data,
                )
                return (
                    self.runs.start(existing.run_id) if existing.status == "CREATED" else existing
                )
            opened = project.snapshot(request.expected_revision)
            assert opened.document is not None
            compilation = compile_project(opened.document)
            if not compilation.result.runnable or compilation.program is None:
                raise ValueError("PROJECT_NOT_RUNNABLE")
            if compilation.result.program_hash != request.expected_program_hash:
                raise ValueError("PROGRAM_HASH_CONFLICT")
            preflight_data(data, {dataset.dataset_name for dataset in compilation.program.datasets})
            probe_python(python, self.root / "probe-cache")
            run = self.runs.prepare(
                project, request.expected_revision, request.expected_program_hash, key, python, data
            )
            if run.status == "CREATED":
                return self.runs.start(run.run_id)
            return run

    def installs(self) -> InstallService:
        with self._mutex:
            self._verify()
            if self._install_service is None:
                self._install_service = InstallService(self.root)
            return self._install_service

    def activity(self) -> dict[str, list[str]]:
        with self._mutex:
            self._verify()
            identities = list(self.runs._ledger.entries)
            return {
                "activeRunIds": [
                    identity
                    for identity in identities
                    if not self.runs.remote.settled(self.runs.get(identity))
                ]
            }

    def close(self) -> None:
        with self._mutex:
            if self._closed:
                return
            self._closing = True
            if self._install_service is not None:
                self._install_service.close()
            self._project_generation += 1
            self._invalidate_identity()
        # SDK workers may need the workspace guard to unwind. Never wait under it.
        self.runs.close()
        if self._connections is not None:
            self._connections.wait_idle()
        with self._mutex:
            for project in self._projects.values():
                project.close()
            self._closed = True
