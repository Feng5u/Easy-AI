"""Opt-in real SSH acceptance through product services. Never a mock stage gate.

Default/check mode performs local checks only. Credentials are one bounded JSON
line on stdin in execute mode; neither argv/config nor reports contain secrets.
"""

from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import stat
import sys
import time
from typing import Callable, Literal, TypeVar, TYPE_CHECKING
from uuid import UUID, uuid4

from pydantic import Field, field_validator

from easyai.domain.contracts import Contract, ProjectDocument
from easyai.domain.environment import Fingerprint, RemotePath
from easyai.domain.ssh import SshEndpoint

if TYPE_CHECKING:
    from easyai.services.local_workspace import LocalWorkspace

OPERATIONS = frozenset(
    {"identity", "probe", "upload", "start", "logs", "disconnect", "resume", "cancel", "artifacts"}
)
T = TypeVar("T")
REPOSITORY = Path(__file__).resolve().parents[3]


class Configuration(Contract):
    endpoint: SshEndpoint
    username: str = Field(min_length=1, max_length=128, pattern=r"^[^\x00-\x20\x7f]+$")
    fingerprint: Fingerprint
    python_path: RemotePath
    data_root: RemotePath
    run_base: RemotePath
    local_root: str = Field(max_length=4096)
    isolated_account: Literal[True]
    authorization_reference: str = Field(min_length=1, max_length=128)
    window_start: datetime
    window_end: datetime
    operations: list[str] = Field(min_length=9, max_length=9)
    max_seconds: int = Field(default=180, ge=30, le=240)

    @field_validator("isolated_account", mode="before")
    @classmethod
    def strict_attestation(cls, value: object) -> Literal[True]:
        if value is not True:
            raise ValueError("Explicit isolated account attestation required")
        return True


class Stop(Exception):
    def __init__(self, status: str, code: int):
        self.status, self.code = status, code


def window(config: Configuration, reserve: int = 0) -> None:
    now = datetime.now(timezone.utc)
    if (
        not config.window_start <= now < config.window_end
        or (config.window_end - now).total_seconds() <= reserve
    ):
        raise Stop("NOT_AUTHORIZED", 3)


def load(path: str | None) -> Configuration:
    if not path:
        raise Stop("NOT_CONFIGURED", 2)
    try:
        selected = Path(path)
        if not selected.is_absolute() or selected.is_symlink():
            raise ValueError()
        if selected.resolve(strict=True) != selected:
            raise ValueError()
        descriptor = os.open(selected, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
        with os.fdopen(descriptor, "rb") as stream:
            info = os.fstat(stream.fileno())
            if (
                not stat.S_ISREG(info.st_mode)
                or info.st_uid != os.getuid()
                or stat.S_IMODE(info.st_mode) & 0o077
                or info.st_size > 16384
            ):
                raise PermissionError()
            raw = stream.read(16385)
            after = os.fstat(stream.fileno())
            current = selected.lstat()
            if (
                len(raw) != info.st_size
                or (info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, info.st_ctime_ns)
                != (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns, after.st_ctime_ns)
                or (info.st_dev, info.st_ino) != (current.st_dev, current.st_ino)
            ):
                raise ValueError()
        config = Configuration.model_validate_json(raw)
        if (
            config.window_start.tzinfo is None
            or config.window_end.tzinfo is None
            or not 0 < (config.window_end - config.window_start).total_seconds() <= 7200
            or set(config.operations) != OPERATIONS
        ):
            raise ValueError()
        root = Path(config.local_root)
        if (
            not root.is_absolute()
            or root.exists()
            or root.is_symlink()
            or root.parent.resolve(strict=True) != root.parent
            or root.is_relative_to(REPOSITORY)
            or selected.resolve().is_relative_to(REPOSITORY)
        ):
            raise ValueError()
        parent = root.parent.stat()
        if parent.st_uid != os.getuid() or stat.S_IMODE(parent.st_mode) & 0o077:
            raise PermissionError()
        parts = config.run_base.split("/")
        if (
            len(parts) < 5
            or parts[-3:-1] != [".easyai", "ssh-acceptance"]
            or str(UUID(parts[-1])) != parts[-1]
            or any(p in ("", ".", "..") for p in parts[1:])
            or config.data_root == config.run_base
            or config.data_root.startswith(config.run_base + "/")
            or config.run_base.startswith(config.data_root + "/")
        ):
            raise ValueError()
        return config
    except FileNotFoundError:
        raise Stop("NOT_CONFIGURED", 2) from None
    except Exception:
        raise Stop("PRECHECK_FAILED", 4) from None


def credentials() -> dict[str, str]:
    try:
        raw = sys.stdin.buffer.readline(70001)
        value = json.loads(raw)
        if (
            len(raw) > 70000
            or type(value) is not dict
            or set(value) not in ({"password"}, {"privateKey"}, {"privateKey", "passphrase"})
            or any(type(v) is not str for v in value.values())
            or not value.get("password", value.get("privateKey"))
            or len(value.get("password", "")) > 1024
            or len(value.get("privateKey", "")) > 65536
            or len(value.get("passphrase", "")) > 1024
        ):
            raise ValueError()
        return value
    except Exception:
        raise Stop("CREDENTIAL_INPUT_REQUIRED", 3) from None


def authorized_workspace(config: Configuration, root: Path) -> "LocalWorkspace":
    from easyai.services.local_workspace import LocalWorkspace

    class WindowWorkspace(LocalWorkspace):
        def _verify(self) -> None:
            # Product identity/lease checks and each upload/owner/artifact I/O
            # guard flow through this callback, including background workers.
            window(config)
            super()._verify()

    return WindowWorkspace(root)


def execute(config: Configuration, secret: dict[str, str]) -> dict[str, object]:
    # Imported only after all local authorization checks, never in default mode.
    from easyai.compiler.pipeline import compile_project
    from easyai.domain.catalog import SOURCE_ROOT
    from easyai.domain.connections import (
        AuthenticationRequest,
        ConnectionProfileInput,
        SessionControl,
    )
    from easyai.domain.data_transfer import (
        TransferPlanRequest,
        TransferBudget,
        TransferConfirmation,
    )
    from easyai.domain.environment import (
        EnvironmentDiscoveryRequest,
        EnvironmentProbeRequest,
        DatasetProbe,
    )
    from easyai.domain.remote_execution import RemoteBindingRequest, RemoteRunStartRequest
    from easyai.domain.ssh import IdentityProbeRequest, IdentityConfirmRequest, HostKeyConfirmation
    from easyai.services.run_views import RunViews

    root = Path(config.local_root)
    root.mkdir(mode=0o700, exist_ok=False)
    workspace = authorized_workspace(config, root / "state")
    stage = "project"
    report: dict[str, object] = {"status": "FAIL", "scope": "real-ssh", "runIds": []}
    active: list[str] = []
    deadline = time.monotonic() + config.max_seconds

    def check() -> None:
        window(config)
        if time.monotonic() >= deadline:
            raise RuntimeError("acceptance budget")

    def wait(read: Callable[[], T], predicate: Callable[[T], bool]) -> T:
        while True:
            check()
            value = read()
            if predicate(value):
                return value
            time.sleep(0.1)

    try:
        folder = root / "project"
        folder.mkdir(mode=0o700)
        session = workspace.create(
            workspace.select("project", folder).selection_id, "SSH acceptance"
        )
        assert session.project is not None
        project_id = session.project.project_id
        profile = workspace.create_connection_profile(
            ConnectionProfileInput(
                alias="explicit isolated acceptance",
                endpoint=config.endpoint,
                username=config.username,
            )
        )

        def authorize() -> SessionControl:
            check()
            identity_id = str(uuid4())
            observed = (
                workspace.identity()
                .probe(
                    IdentityProbeRequest(
                        project_id=project_id, request_id=identity_id, endpoint=config.endpoint
                    )
                )
                .observation
            )
            if observed.fingerprint != config.fingerprint or observed.trust_state == "changed":
                raise RuntimeError("pin mismatch")
            if observed.trust_state == "unknown":
                assert observed.challenge_id is not None
                check()
                workspace.identity().confirm(
                    IdentityConfirmRequest(
                        project_id=project_id,
                        request_id=identity_id,
                        confirmation=HostKeyConfirmation(
                            challenge_id=observed.challenge_id, fingerprint=config.fingerprint
                        ),
                    )
                )
            request = AuthenticationRequest(
                project_id=project_id,
                request_id=str(uuid4()),
                identity_request_id=identity_id,
                expected_fingerprint=config.fingerprint,
                username=config.username,
                target_id=profile.target_id,
                target_revision=profile.revision,
            )
            check()
            manager = workspace.connections()
            auth = (
                manager.authenticate_password(request, secret["password"])
                if "password" in secret
                else manager.authenticate_private_key(
                    request, secret["privateKey"], secret.get("passphrase", "")
                )
            )
            return SessionControl(project_id=project_id, connection_id=auth.scope.connection_id)

        stage = "identity_auth"
        control = authorize()
        stage = "explicit_upload"
        source = root / "upload-fixture"
        source.mkdir(mode=0o700)
        with (source / "acceptance.txt").open("xb") as output:
            os.fchmod(output.fileno(), 0o600)
            output.write(b"Easy-AI SSH protocol acceptance\n")
        upload_request = TransferPlanRequest(
            **control.model_dump(),
            expected_revision=1,
            data_selection_id=workspace.select("data", source).selection_id,
            budget=TransferBudget(max_files=1, max_bytes=1024, seconds=30),
        )
        plan = workspace.plan_transfer(upload_request)
        check()
        confirmation = TransferConfirmation(
            **control.model_dump(), plan_id=plan.plan_id, plan_hash=plan.plan_hash, confirmed=True
        )
        workspace.transfers().confirm(confirmation)
        uploaded = wait(
            lambda: workspace.transfers().get(plan.plan_id, control),
            lambda j: j.status in {"COMPLETED", "FAILED", "CANCELLED", "CLEANUP_PENDING"},
        )
        assert uploaded.status == "COMPLETED" and not uploaded.data_ready
        check()
        recovery = workspace.plan_transfer(upload_request, plan.plan_id)
        assert recovery.missing_files == 0 and recovery.reused_bytes == uploaded.total_bytes
        report["uploadSlotId"] = plan.plan_id

        def prepare(epochs: int) -> RemoteRunStartRequest:
            check()
            document = json.loads(
                (SOURCE_ROOT / "packages/contracts/fixtures/mnist-figures.json").read_bytes()
            )
            current_session = workspace.current()
            assert current_session is not None and current_session.project is not None
            current = current_session.project
            document.update(projectId=project_id, name="SSH acceptance", revision=current.revision)

            document["settings"]["executionMode"] = "quick" if epochs == 1 else "full"

            def adjust(value: object) -> None:
                if isinstance(value, dict):
                    if value.get("type") == "train.loop":
                        value["fields"]["EPOCHS"] = epochs
                    for item in value.values():
                        adjust(item)
                elif isinstance(value, list):
                    for item in value:
                        adjust(item)

            adjust(document)
            saved = workspace.save(
                project_id, ProjectDocument.model_validate(document), current.revision
            ).project
            assert saved is not None
            compiled = compile_project(saved)
            assert compiled.result.runnable and compiled.result.code is not None
            assert "download=False" in compiled.result.code
            environment = workspace.connections().environments(
                EnvironmentDiscoveryRequest(
                    **control.model_dump(), request_id=str(uuid4()), python_path=config.python_path
                )
            )
            check()
            discovery = environment.discover(
                EnvironmentDiscoveryRequest(
                    **control.model_dump(), request_id=str(uuid4()), python_path=config.python_path
                )
            )
            selected = [e for e in discovery.environments if e.location == config.python_path]
            assert len(selected) == 1
            probe_id = str(uuid4())
            check()
            probe = environment.probe(
                EnvironmentProbeRequest(
                    **control.model_dump(),
                    request_id=probe_id,
                    environment_id=selected[0].environment_id,
                    dataset=DatasetProbe(name="MNIST", data_root=config.data_root),
                )
            )
            assert probe.environment_ready and probe.data_ready is True
            check()
            binding = workspace.bind_remote(
                project_id,
                RemoteBindingRequest(
                    **control.model_dump(),
                    request_id=str(uuid4()),
                    expected_revision=saved.revision,
                    expected_program_hash=compiled.result.program_hash,
                    probe_request_id=probe_id,
                    run_base=config.run_base,
                ),
            )
            return RemoteRunStartRequest(
                runner="ssh",
                binding_id=binding.binding_id,
                expected_revision=saved.revision,
                expected_program_hash=compiled.result.program_hash,
            )

        stage = "success_start"
        request = prepare(1)
        key = str(uuid4())
        check()
        run = workspace.start(project_id, request, key)
        active.append(run.run_id)
        report["runIds"] = active.copy()
        assert workspace.start(project_id, request, key).run_id == run.run_id
        running = wait(
            lambda: workspace.runs.get(run.run_id),
            lambda r: r.status not in {"CREATED", "PRECHECKING", "STAGING", "STARTING"},
        )
        assert running.status == "RUNNING"
        stage = "disconnect_resume"
        workspace.connections().close(control)
        workspace.connections().wait_idle()
        control = authorize()
        check()
        workspace.resume_remote(run.run_id, control)
        stage = "logs_artifacts"
        completed = wait(
            lambda: workspace.runs.get(run.run_id),
            lambda r: r.status in {"SUCCEEDED", "FAILED", "CANCELLED"} or r.sync_state == "error",
        )
        assert completed.status == "SUCCEEDED" and completed.sync_state == "complete"
        events = workspace.runs.events(run.run_id)
        assert len([e for e in events if e.type == "process_exited"]) == 1
        assert any(e.type == "epoch_completed" for e in events)
        view = RunViews(workspace.runs)
        out_cursor = err_cursor = 0
        while True:
            check()
            logs = view.logs(run.run_id, out_cursor, err_cursor)
            assert logs.stdout_after >= out_cursor and logs.stderr_after >= err_cursor
            out_cursor, err_cursor = logs.stdout_after, logs.stderr_after
            assert out_cursor + err_cursor <= 1024 * 1024
            if logs.done:
                break
        assert len([e for e in events if e.type == "runtime_started"]) == 1
        assert completed.config.bundle_hash == run.config.bundle_hash
        assert completed.remote is not None and completed.remote.artifacts_verified
        figures = [a for a in view.artifacts(run.run_id) if a.kind == "figure"]
        assert figures and all(a.sync_state == "ready" for a in figures)
        for figure in figures:
            check()
            content = view.image(run.run_id, figure.artifact_id)
            assert (
                len(content) == figure.size_bytes
                and hashlib.sha256(content).hexdigest() == figure.sha256
            )
        report["successRunId"] = run.run_id
        stage = "cancel_start"
        request = prepare(2)
        check()
        cancelled = workspace.start(project_id, request, str(uuid4()))
        active.append(cancelled.run_id)
        report["runIds"] = active.copy()
        wait(
            lambda: workspace.runs.get(cancelled.run_id),
            lambda r: r.status == "RUNNING" or r.status in {"SUCCEEDED", "FAILED"},
        )
        stage = "cancel"
        check()
        workspace.cancel_run(workspace.run_scope(cancelled.run_id))
        final = wait(
            lambda: workspace.runs.get(cancelled.run_id),
            lambda r: r.status in {"CANCELLED", "FAILED", "SUCCEEDED"},
        )
        assert (
            final.status == "CANCELLED"
            and final.remote is not None
            and final.remote.execution_state == "CANCELLED"
        )
        cancelled_events = workspace.runs.events(cancelled.run_id)
        assert len([e for e in cancelled_events if e.type == "process_exited"]) == 1
        report.update(status="PASS", cancelRunId=cancelled.run_id, checkedFigures=len(figures))
    except Exception:
        report.update(
            status="FAIL",
            stage=stage,
            detail="fixed acceptance failure; inspect private product state",
        )
    finally:
        # Preserve evidence and remote outputs. Only cancel exact owned runs while
        # still within the explicit window; never delete directories or kill PIDs.
        cleanup = "quiet"
        # A consuming start may lose its return value; recover exact owned IDs
        # from this newly created product ledger before reporting or cancelling.
        active = list(workspace.runs._ledger.entries)
        report["runIds"] = active.copy()
        for run_id in active:
            try:
                window(config)
                run = workspace.runs.get(run_id)
                if run.status not in {"SUCCEEDED", "FAILED", "CANCELLED"}:
                    workspace.cancel_run(workspace.run_scope(run_id))
                    cleanup = "cancel_requested_not_proven_quiet"
            except Exception:
                cleanup = "unknown"
        try:
            workspace.close()
        except Exception:
            cleanup = "unknown"
        secret.clear()
        report["cleanup"] = cleanup
        if cleanup != "quiet":
            report["status"] = "FAIL"
        with (root / "acceptance.json").open("x", encoding="utf-8") as report_output:
            os.fchmod(report_output.fileno(), 0o600)
            json.dump(report, report_output, indent=2)
            report_output.write("\n")
    return report


def main() -> int:
    try:
        args = sys.argv[1:]
        if args not in ([], ["--check"], ["--execute"]):
            raise Stop("PRECHECK_FAILED", 4)
        if os.name != "posix":
            raise Stop("PRECHECK_FAILED", 4)
        config = load(os.environ.get("EASYAI_SSH_TEST_CONFIG"))
        window(config, config.max_seconds + 30)
        if args != ["--execute"]:
            raise Stop(
                "READY_NOT_RUN" if args == ["--check"] else "NOT_AUTHORIZED", 5 if args else 3
            )
        secret = credentials()
        try:
            window(config, config.max_seconds + 30)
            report = execute(config, secret)
        finally:
            secret.clear()
        print(json.dumps(report))
        return 0 if report["status"] == "PASS" else 1
    except Stop as error:
        print(json.dumps({"status": "NOT RUN", "reason": error.status}))
        return error.code
    except Exception:
        print(json.dumps({"status": "FAIL", "reason": "FIXED_RUNNER_FAILURE"}))
        return 1


if __name__ == "__main__":
    sys.exit(main())
