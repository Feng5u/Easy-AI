"""Real fixture processes exercising log short writes and persistence failures."""

import errno
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from typing import BinaryIO, cast
import unittest
from unittest.mock import patch

from easyai.runtime.supervisor import ManagedSupervisor


class LimitedLog:
    """Keep real files and fsync while controlling one raw write's progress."""

    def __init__(self, raw: BinaryIO, fault: str | None = None):
        self.raw = raw
        self.fault = fault
        self.writes = 0

    def write(self, content):
        self.writes += 1
        if self.fault == "zero":
            return 0
        if self.fault == "none":
            return None
        if self.fault == "full" and self.writes > 1:
            raise OSError(errno.ENOSPC, "fixture log is full")
        return self.raw.write(content[:13])

    def flush(self):
        if self.fault == "flush":
            raise OSError(errno.EIO, "fixture log flush failed")
        return self.raw.flush()

    def fileno(self):
        return self.raw.fileno()

    def close(self):
        self.raw.close()
        if self.fault == "close":
            raise OSError(errno.EIO, "fixture log close failed")


class ManagedLogWrites(unittest.TestCase):
    def supervisor(self, root: Path, source: str, **kwargs):
        run = root / "run 中文"
        run.mkdir()
        return ManagedSupervisor(
            run,
            "log-fixture",
            [sys.executable, "-I", "-B", "-c", source],
            root,
            cancel_grace=0.08,
            **kwargs,
        )

    def wrap_logs(self, supervisor, fault=None, target=None):
        original = supervisor._open_log

        def open_log(name):
            return cast(
                BinaryIO,
                LimitedLog(original(name), fault if name == target else None),
            )

        return patch.object(supervisor, "_open_log", side_effect=open_log)

    def test_short_writes_preserve_both_logs_and_exact_optional_limit(self):
        stdout = ("stdout 中文\n" * 300).encode()
        stderr = ("stderr 中文\n" * 300).encode()
        completion = (
            "@@EASYAI_EVENT@@"
            + json.dumps({"type": "pipeline_completed", "blockId": None, "payload": {}})
            + "\n"
        ).encode()
        source = (
            f"import os\nos.write(1, {stdout!r})\nos.write(2, {stderr!r})\n"
            f"os.write(1, {completion!r})\n"
        )
        for limit in (None, 1024):
            with self.subTest(limit=limit), tempfile.TemporaryDirectory() as directory:
                supervisor = self.supervisor(Path(directory), source, max_log_bytes=limit)
                try:
                    with self.wrap_logs(supervisor):
                        supervisor.start()
                        supervisor.wait(5)
                    self.assertEqual(supervisor.status, "COMPLETED")
                    self.assertEqual(supervisor.exit_code, 0)
                    for name, expected in (("train.log", stdout), ("stderr.log", stderr)):
                        saved = (supervisor.run_root / "logs" / name).read_bytes()
                        self.assertEqual(saved, expected if limit is None else expected[:limit])
                    if limit is not None:
                        self.assertEqual(sorted(supervisor._log_bytes.values()), [limit, limit])
                    self.assertEqual(
                        [event.type for event in supervisor.events()],
                        ["pipeline_completed", "process_exited"],
                    )
                finally:
                    supervisor.close()
                self.assertTrue(supervisor.quiescent)

    def test_failed_writes_stop_the_child_without_a_cancel_request(self):
        content = b"fixture output that must be saved\n"
        for name, descriptor in (("train.log", 1), ("stderr.log", 2)):
            for fault in ("zero", "none", "full"):
                with self.subTest(log=name, fault=fault):
                    with tempfile.TemporaryDirectory() as directory:
                        source = (
                            "import os, signal, time\n"
                            "if os.name == 'posix': signal.signal(signal.SIGTERM, signal.SIG_IGN)\n"
                            f"os.write({descriptor}, {content!r})\ntime.sleep(30)\n"
                        )
                        supervisor = self.supervisor(Path(directory), source, max_log_bytes=1024)
                        try:
                            with self.wrap_logs(supervisor, fault, name):
                                supervisor.start()
                                supervisor.wait(2)
                            self.assertEqual(supervisor.status, "FAILED")
                            self.assertIsNotNone(supervisor.exit_code)
                            events = supervisor.events()
                            self.assertEqual(events[-1].type, "process_exited")
                            self.assertTrue(any(e.type == "runtime_error" for e in events))
                            self.assertFalse((supervisor.run_root / "cancel.request.json").exists())
                            self.assertFalse(supervisor._cancel_requested.is_set())
                            self.assertEqual(
                                (supervisor.run_root / "logs" / name).read_bytes(),
                                content[:13] if fault == "full" else b"",
                            )
                            self.assertEqual(
                                list(supervisor._log_bytes.values()),
                                [13] if fault == "full" else [],
                            )
                        finally:
                            supervisor.close()
                        self.assertTrue(supervisor.quiescent)

    @unittest.skipUnless(
        sys.platform == "linux" and hasattr(os, "memfd_create"),
        "Anonymous FileIO size-limit regression requires Linux memfd",
    )
    def test_real_fileio_short_write_cannot_return_success(self):
        source_root = Path(__file__).resolve().parents[1] / "src"
        source = f"""
import json, os, resource, signal, sys
sys.path.insert(0, {str(source_root)!r})
from easyai.runtime.managed import ManagedProcess
descriptor = os.memfd_create('managed-log-fixture', os.MFD_CLOEXEC)
with os.fdopen(descriptor, 'wb', buffering=0) as log:
    signal.signal(signal.SIGXFSZ, signal.SIG_IGN)
    resource.setrlimit(resource.RLIMIT_FSIZE, (3, 3))
    process = object.__new__(ManagedProcess)
    process._max_log_bytes = None
    process._log_bytes = {{}}
    failed = False
    try:
        process._write_log(log, b'0123456789')
    except OSError:
        failed = True
    os.fsync(log.fileno())
    print(json.dumps({{'failed': failed, 'savedBytes': os.fstat(log.fileno()).st_size}}))
"""
        result = subprocess.run(
            [sys.executable, "-I", "-B", "-c", source],
            capture_output=True,
            text=True,
            timeout=5,
            check=True,
        )
        self.assertEqual(json.loads(result.stdout), {"failed": True, "savedBytes": 3})

    def test_flush_or_close_failure_stops_a_child_that_closed_its_pipe(self):
        for name, descriptor in (("train.log", 1), ("stderr.log", 2)):
            for fault in ("flush", "close"):
                with self.subTest(log=name, fault=fault):
                    with tempfile.TemporaryDirectory() as directory:
                        source = f"import os, time\nos.close({descriptor})\ntime.sleep(30)\n"
                        supervisor = self.supervisor(Path(directory), source)
                        try:
                            with self.wrap_logs(supervisor, fault, name):
                                supervisor.start()
                                supervisor.wait(2)
                            self.assertEqual(supervisor.status, "FAILED")
                            self.assertIsNotNone(supervisor.exit_code)
                            self.assertTrue(
                                any(e.type == "runtime_error" for e in supervisor.events())
                            )
                            self.assertFalse((supervisor.run_root / "cancel.request.json").exists())
                        finally:
                            supervisor.close()
                        self.assertTrue(supervisor.quiescent)


if __name__ == "__main__":
    unittest.main()
