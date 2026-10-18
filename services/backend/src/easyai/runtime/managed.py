"""Application-owned subprocess supervision; training children need no Easy-AI package."""

import json
import os
from pathlib import Path
import signal
import stat
import subprocess
import tempfile
import threading
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from typing import Any, BinaryIO, Generic, Protocol, Self, TypeVar

MAX_LINE_BYTES = 64 * 1024


class EventLike(Protocol):
    def model_copy(self, *, deep: bool = False) -> Self: ...


E = TypeVar("E", bound=EventLike)


class Journal(Protocol[E]):
    def append(self, event_type: str, block_id: str | None, payload: dict[str, Any]) -> E: ...
    def after(self, seq: int) -> list[E]: ...
    def close(self) -> None: ...


PREFIX = b"@@EASYAI_EVENT@@"
CHILD_TYPES = frozenset(
    {
        "runtime_started",
        "device_selected",
        "progress",
        "epoch_completed",
        "artifact_created",
        "runtime_error",
        "pipeline_cancelled",
        "pipeline_completed",
    }
)
TERMINAL = frozenset({"COMPLETED", "FAILED", "CANCELLED"})


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate protocol key")
        result[key] = value
    return result


class ManagedProcess(Generic[E]):
    """One managed launch, one durable runtime writer, and bounded cancellation.

    COMPLETED means exit zero plus valid completion protocol; it is deliberately
    not training SUCCEEDED. RunService must still verify required artifacts.
    POSIX cleanup controls the new process group. Windows controls only the direct
    child, and makes no claim that grandchildren have been terminated.
    """

    def __init__(
        self,
        run_root: Path,
        run_id: str,
        argv: list[str],
        cwd: Path,
        environment: dict[str, str] | None = None,
        cancel_grace: float = 0.5,
        *,
        journal_factory: Callable[[Path, str], Journal[E]],
        max_log_bytes: int | None = None,
        inherit_environment: bool = True,
    ) -> None:
        if run_root.is_symlink() or not run_root.is_dir():
            raise ValueError("Supervisor requires an existing nonsymlink run root")
        if not run_id or not argv or any(not isinstance(arg, str) or "\x00" in arg for arg in argv):
            raise ValueError("Invalid supervisor launch")
        if not 0.01 <= cancel_grace <= 30:
            raise ValueError("Cancellation grace must be 0.01..30 seconds")
        self._journal_factory = journal_factory
        if max_log_bytes is not None and not 1024 <= max_log_bytes <= 16 * 1024 * 1024:
            raise ValueError("Managed log limit must be 1 KiB..16 MiB")
        self._max_log_bytes = max_log_bytes
        self._log_bytes: dict[int, int] = {}
        self.run_root = run_root.resolve(strict=True)
        self.run_id = run_id
        self.argv = list(argv)
        self.cwd = cwd.resolve(strict=True)
        if not self.cwd.is_dir():
            raise ValueError("Supervisor cwd must be a directory")
        self.inherit_environment = inherit_environment
        self.environment = None if environment is None else dict(environment)
        self.cancel_grace = cancel_grace
        self._status = "CREATED"
        self.exit_code: int | None = None
        self._mutex = threading.RLock()
        self._done = threading.Event()
        self._cancel_requested = threading.Event()
        self._process: subprocess.Popen[bytes] | None = None
        self._journal: Journal[E] | None = None
        self._closed_events: list[E] | None = None
        self._threads: list[threading.Thread] = []
        self._monitor: threading.Thread | None = None
        self._cancel_thread: threading.Thread | None = None
        self._fault = False
        self._completed = False
        self._cancelled_event = False
        self._started = False
        self._last_epoch = 0
        self._terminal_protocol = False
        self._closed = False

    @property
    def status(self) -> str:
        with self._mutex:
            return self._status

    @contextmanager
    def snapshot(self) -> Iterator[tuple[str, bool, int | None]]:
        """Freeze journal appends and lifecycle while a reader captures stream prefixes."""
        with self._mutex:
            yield self._status, self._done.is_set(), self.exit_code

    def _append(self, event_type: str, block_id: str | None, payload: dict[str, Any]) -> E:
        journal = self._journal
        if journal is None:
            raise RuntimeError("Supervisor journal is not open")
        with self._mutex:
            return journal.append(event_type, block_id, payload)

    def _protocol_fault(self, message: str) -> None:
        with self._mutex:
            self._fault = True
        try:
            self._append(
                "runtime_error",
                None,
                {"code": "RUNTIME_PROTOCOL_INVALID", "message": message[:1024]},
            )
        except Exception:
            # An uncertain journal remains failed; never manufacture success.
            with self._mutex:
                self._fault = True

    def _open_log(self, name: str) -> BinaryIO:
        path = self.run_root / "logs" / name
        descriptor = os.open(
            path,
            os.O_CREAT
            | os.O_EXCL
            | os.O_WRONLY
            | getattr(os, "O_NOFOLLOW", 0)
            | getattr(os, "O_BINARY", 0),
            0o600,
        )
        try:
            if not stat.S_ISREG(os.fstat(descriptor).st_mode):
                raise ValueError("Supervisor log must be a regular file")
            if os.name == "posix":
                parent = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
                try:
                    os.fsync(parent)
                finally:
                    os.close(parent)
        except BaseException:
            os.close(descriptor)
            raise
        return os.fdopen(descriptor, "wb", buffering=0)

    def start(self) -> None:
        with self._mutex:
            if self._started or self._closed:
                raise RuntimeError("Supervisor start is single-use")
            self._started = True
            self._status = "STARTING"
        try:
            logs = self.run_root / "logs"
            if logs.is_symlink():
                raise ValueError("Supervisor logs cannot be a symlink")
            logs.mkdir(exist_ok=True)
            journal = self._journal_factory(logs / "runtime-events.jsonl", self.run_id)
            self._journal = journal
            if journal.after(0):
                journal.close()
                self._journal = None
                raise ValueError("Refusing to relaunch a recorded run")
        except BaseException:
            self._status = "FAILED"
            self._done.set()
            raise
        stdout_log: BinaryIO | None = None
        stderr_log: BinaryIO | None = None
        try:
            stdout_log = self._open_log("train.log")
            stderr_log = self._open_log("stderr.log")
            env = os.environ.copy() if self.inherit_environment else {}
            if self.environment is not None:
                env.update(self.environment)
            env["PYTHONUNBUFFERED"] = "1"
            process = subprocess.Popen(
                self.argv,
                cwd=self.cwd,
                env=env,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                start_new_session=os.name == "posix",
                shell=False,
            )
            self._process = process
            assert process.stdout is not None and process.stderr is not None
            self._status = "RUNNING"
            self._threads = [
                threading.Thread(
                    target=self._drain_stdout, args=(process.stdout, stdout_log), daemon=True
                ),
                threading.Thread(
                    target=self._drain_stderr, args=(process.stderr, stderr_log), daemon=True
                ),
            ]
            for thread in self._threads:
                thread.start()
            self._monitor = threading.Thread(target=self._finish, daemon=True)
            self._monitor.start()
        except BaseException:
            if self._process is not None:
                self._signal_group(force=True)
                self.exit_code = self._process.wait(timeout=5)
                for thread in self._threads:
                    if thread.ident is not None:
                        thread.join(2)
                for pipe in (self._process.stdout, self._process.stderr):
                    if pipe is not None:
                        pipe.close()
            for stream in (stdout_log, stderr_log):
                if stream is not None:
                    stream.close()
            self._status = "FAILED"
            self._fault = True
            self._append(
                "process_spawn_failed" if self._process is None else "process_exited",
                None,
                {"code": "PROCESS_SPAWN_FAILED", "spawnFailed": True}
                if self._process is None
                else {
                    "exitCode": self.exit_code,
                    "managementFailed": True,
                },
            )
            self._done.set()
            raise

    def _write_log(self, log: BinaryIO, content: bytes) -> None:
        if self._max_log_bytes is not None:
            used = self._log_bytes.get(id(log), 0)
            content = content[: max(0, self._max_log_bytes - used)]
            self._log_bytes[id(log)] = used + len(content)
        log.write(content)

    def _line(self, raw: bytes, log: BinaryIO, complete: bool = True) -> None:
        if not raw.startswith(PREFIX):
            self._write_log(log, raw)
            return
        try:
            if not complete:
                raise ValueError("Unterminated runtime protocol line")
            payload = json.loads(
                raw[len(PREFIX) :].decode("utf-8"), object_pairs_hook=_unique_object
            )
            if not isinstance(payload, dict) or set(payload) != {"type", "blockId", "payload"}:
                raise ValueError("Protocol must contain only type, blockId and payload")
            if payload["type"] not in CHILD_TYPES:
                raise ValueError("Child attempted an unsupported or supervisor-owned event")
            block_id = payload["blockId"]
            if block_id is not None and (
                not isinstance(block_id, str) or not 1 <= len(block_id) <= 256
            ):
                raise ValueError("Invalid protocol blockId")
            if not isinstance(payload["payload"], dict):
                raise ValueError("Invalid protocol payload")
            if self._terminal_protocol and payload["type"] != "runtime_error":
                raise ValueError("Runtime event follows terminal protocol")
            if payload["type"] == "epoch_completed":
                if payload["payload"].get("epoch") != self._last_epoch + 1:
                    raise ValueError("Runtime epochs must be consecutive and unique")
            self._append(payload["type"], block_id, payload["payload"])
            if payload["type"] == "epoch_completed":
                self._last_epoch += 1
            if payload["type"] in {"pipeline_completed", "pipeline_cancelled"}:
                self._terminal_protocol = True
            with self._mutex:
                if payload["type"] == "pipeline_completed":
                    self._completed = True
                elif payload["type"] == "pipeline_cancelled":
                    self._cancelled_event = True
                elif payload["type"] == "runtime_error":
                    self._fault = True
        except Exception as error:
            self._write_log(log, raw)
            self._protocol_fault(str(error))

    def _drain_stdout(self, stream: BinaryIO, log: BinaryIO) -> None:
        pending = b""
        overflow = False
        try:
            while True:
                chunk = os.read(stream.fileno(), 16384)
                if not chunk:
                    break
                for part in chunk.splitlines(keepends=True):
                    # Only LF terminates a protocol record; splitlines also splits CR,
                    # therefore pending remains until an actual LF is observed.
                    if overflow:
                        self._write_log(log, part)
                        if part.endswith(b"\n"):
                            overflow = False
                        continue
                    pending += part
                    if len(pending) > MAX_LINE_BYTES:
                        if pending.startswith(PREFIX):
                            self._protocol_fault("Runtime protocol line exceeds 64 KiB")
                        self._write_log(log, pending)
                        pending = b""
                        overflow = not part.endswith(b"\n")
                    elif pending.endswith(b"\n"):
                        self._line(pending, log)
                        pending = b""
            if pending:
                self._line(pending, log, complete=False)
        except Exception as error:
            self._protocol_fault(f"stdout drain failed: {error}")
        finally:
            self._close_streams(stream, log)

    def _drain_stderr(self, stream: BinaryIO, log: BinaryIO) -> None:
        try:
            while chunk := os.read(stream.fileno(), 16384):
                self._write_log(log, chunk)
        except Exception as error:
            self._protocol_fault(f"stderr drain failed: {error}")
        finally:
            self._close_streams(stream, log)

    def _close_streams(self, stream: BinaryIO, log: BinaryIO) -> None:
        try:
            stream.close()
            log.flush()
            os.fsync(log.fileno())
        except Exception:
            self._protocol_fault("Managed log persistence failed")
        finally:
            try:
                log.close()
            except Exception:
                self._protocol_fault("Managed log close failed")

    def _signal_group(self, force: bool = False) -> None:
        process = self._process
        if process is None or self._done.is_set():
            return
        try:
            if os.name == "posix":
                os.killpg(process.pid, signal.SIGKILL if force else signal.SIGTERM)
            elif process.poll() is None:
                if force:
                    process.kill()
                else:
                    process.terminate()
        except ProcessLookupError:
            pass

    def _cancel(self) -> None:
        if self._done.wait(self.cancel_grace):
            return
        self._signal_group()
        if self._done.wait(self.cancel_grace):
            return
        self._signal_group(force=True)

    def request_cancel(self) -> None:
        with self._mutex:
            process = self._process
            if (
                self._closed
                or process is None
                or self._status in TERMINAL
                or process.poll() is not None
            ):
                return
            if self._cancel_requested.is_set():
                return
            request = self.run_root / "cancel.request.json"
            if request.is_symlink():
                raise ValueError("Cancellation target cannot be a symlink")
            descriptor, temporary = tempfile.mkstemp(prefix=".cancel-", dir=self.run_root)
            try:
                with os.fdopen(descriptor, "w", encoding="utf-8") as output:
                    json.dump({"runId": self.run_id}, output)
                    output.flush()
                    os.fsync(output.fileno())
                try:
                    os.link(temporary, request)
                except FileExistsError:
                    if (
                        request.is_symlink()
                        or not request.is_file()
                        or request.stat().st_size > 4096
                    ):
                        raise ValueError("Cancellation request already exists and is unsafe")
                    existing = json.loads(request.read_bytes())
                    if existing != {"runId": self.run_id}:
                        raise ValueError("Cancellation request belongs to another run")
            finally:
                Path(temporary).unlink(missing_ok=True)
            self._cancel_requested.set()
            self._status = "CANCELLING"
            self._cancel_thread = threading.Thread(target=self._cancel, daemon=True)
            self._cancel_thread.start()

    def _finish(self) -> None:
        process = self._process
        assert process is not None
        try:
            code = process.wait()
            # A completed leader must not leave managed grandchildren holding pipes.
            # This targets only the dedicated group created by this supervisor.
            self._signal_group()
            for thread in self._threads:
                thread.join(self.cancel_grace)
            if any(thread.is_alive() for thread in self._threads):
                self._signal_group(force=True)
                for thread in self._threads:
                    thread.join(max(1.0, self.cancel_grace))
            if any(thread.is_alive() for thread in self._threads):
                self._protocol_fault("Managed pipes did not close after group termination")
                with self._mutex:
                    self._status = "CLEANUP_PENDING"
                # Do not announce process_exited before both readers actually drain.
                # A process that escaped the owned group remains a visible blocker.
                for thread in self._threads:
                    thread.join()
            with self._mutex:
                self._append("process_exited", None, {"exitCode": code})
                self.exit_code = code
                if self._fault:
                    self._status = "FAILED"
                elif code == 0 and self._completed and not self._cancelled_event:
                    self._status = "COMPLETED"
                elif self._cancel_requested.is_set() or self._cancelled_event:
                    self._status = "CANCELLED"
                else:
                    self._status = "FAILED"
                self._done.set()
        except Exception:
            with self._mutex:
                self.exit_code = process.returncode
                self._fault = True
                self._status = "FAILED"
                self._done.set()
        finally:
            self._done.set()

    def wait(self, timeout: float | None = None) -> int | None:
        if not self._started:
            raise RuntimeError("Supervisor has not started")
        return self.exit_code if self._done.wait(timeout) else None

    def events(self) -> list[E]:
        with self._mutex:
            if self._closed_events is not None:
                return [event.model_copy(deep=True) for event in self._closed_events]
            return self._journal.after(0) if self._journal is not None else []

    @property
    def quiescent(self) -> bool:
        with self._mutex:
            return (
                self._closed
                and (self._process is None or self._process.poll() is not None)
                and all(not thread.is_alive() for thread in self._threads)
                and (self._monitor is None or not self._monitor.is_alive())
                and (self._cancel_thread is None or not self._cancel_thread.is_alive())
            )

    def close(self) -> None:
        if self._closed:
            return
        try:
            self.request_cancel()
        except (OSError, ValueError):
            self._cancel_requested.set()
            self._signal_group(force=True)
        if self._process is not None:
            self._done.wait(max(5.0, 4 * self.cancel_grace))
            if not self._done.is_set():
                self._signal_group(force=True)
                self._done.wait(5.0)
            if not self._done.is_set():
                raise RuntimeError("Managed process cleanup is still pending")
        if self._cancel_thread is not None:
            self._cancel_thread.join(max(1.0, 2 * self.cancel_grace))
        if self._monitor is not None and self._monitor is not threading.current_thread():
            self._monitor.join(max(1.0, 2 * self.cancel_grace))
        if (
            any(thread.is_alive() for thread in self._threads)
            or (self._monitor is not None and self._monitor.is_alive())
            or (self._cancel_thread is not None and self._cancel_thread.is_alive())
        ):
            raise RuntimeError("Managed process cleanup is still pending")
        with self._mutex:
            if self._journal is not None:
                try:
                    self._closed_events = self._journal.after(0)
                finally:
                    self._journal.close()
                    self._journal = None
            self._closed = True
