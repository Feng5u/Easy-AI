"""Real stdlib fixture processes; these never simulate production training metrics."""

import json
import os
from pathlib import Path
import sys
import time

import pytest

from easyai.runtime.supervisor import ManagedSupervisor

HEADER = """import json, os, sys, time
PREFIX = '@@EASYAI_EVENT@@'
def event(kind, payload=None):
    print(PREFIX + json.dumps({'type': kind, 'blockId': 'fixture', 'payload': payload or {}}, ensure_ascii=False), flush=True)
"""


def make(tmp_path: Path, source: str, **kwargs) -> ManagedSupervisor:
    run = tmp_path / "run 中文"
    run.mkdir()
    script = tmp_path / "fixture.py"
    script.write_text(HEADER + source, encoding="utf-8")
    return ManagedSupervisor(
        run, "fixture-run-id", [sys.executable, str(script)], tmp_path, cancel_grace=0.08, **kwargs
    )


def finish(supervisor: ManagedSupervisor, timeout=8):
    supervisor.wait(timeout)
    assert supervisor.status in {"FAILED", "CANCELLED", "COMPLETED"}
    result = supervisor.events()
    assert result[-1].type == "process_exited"
    assert len([event for event in result if event.type == "process_exited"]) == 1
    assert [event.seq for event in result] == list(range(1, len(result) + 1))
    assert all(
        event.source_seq == event.seq and event.run_id == "fixture-run-id" for event in result
    )
    return result


def test_concurrent_large_pipes_and_partial_utf8_protocol(tmp_path):
    supervisor = make(
        tmp_path,
        """
event('runtime_started')
os.write(2, b'e' * (2 * 1024 * 1024))
os.write(1, b'n' * (1024 * 1024) + b'\\n')
raw = (PREFIX + json.dumps({'type': 'progress', 'blockId': 'fixture', 'payload': {'message': '中文'}}, ensure_ascii=False) + '\\n').encode()
for byte in raw:
    os.write(1, bytes([byte]))
event('pipeline_completed')
""",
    )
    try:
        supervisor.start()
        events = finish(supervisor)
        assert supervisor.status == "COMPLETED" and supervisor.exit_code == 0
        assert (supervisor.run_root / "logs/stderr.log").stat().st_size == 2 * 1024 * 1024
        assert (supervisor.run_root / "logs/train.log").stat().st_size == 1024 * 1024 + 1
        assert (
            next(event for event in events if event.type == "progress").payload["message"] == "中文"
        )
    finally:
        supervisor.close()
    assert supervisor.events() == events
    with pytest.raises(RuntimeError, match="single-use"):
        supervisor.start()


@pytest.mark.parametrize(
    "source",
    [
        "print(PREFIX + '{broken', flush=True)\nevent('pipeline_completed')\n",
        "print(PREFIX + json.dumps({'type':'epoch_completed','blockId':'fixture','payload':{'epoch':1}}), flush=True)\nevent('pipeline_completed')\n",
        "print(PREFIX + json.dumps({'type':'pipeline_completed','blockId':'fixture','payload':{},'runId':'forged','seq':999}), flush=True)\n",
        "event('process_exited', {'exitCode':0})\nevent('pipeline_completed')\n",
        "event('status_changed', {'status':'SUCCEEDED'})\nevent('pipeline_completed')\n",
        'print(PREFIX + \'{"type":"pipeline_completed","type":"pipeline_completed","blockId":null,"payload":{}}\', flush=True)\n',
        "os.write(1, (PREFIX + 'x' * 100000 + '\\n').encode())\nevent('pipeline_completed')\n",
        "os.write(1, (PREFIX + json.dumps({'type':'pipeline_completed','blockId':'fixture','payload':{}})).encode())\n",
    ],
)
def test_invalid_protocol_is_logged_and_prevents_completion(tmp_path, source):
    supervisor = make(tmp_path, source)
    try:
        supervisor.start()
        events = finish(supervisor)
        assert supervisor.status == "FAILED"
        assert not any(event.type == "epoch_completed" for event in events)
        assert any(event.type == "runtime_error" for event in events)
        assert b"@@EASYAI_EVENT@@" in (supervisor.run_root / "logs/train.log").read_bytes()
    finally:
        supervisor.close()


@pytest.mark.parametrize(
    "source",
    [
        "print('ordinary log only', flush=True)\n",
        "event('runtime_error', {'message':'failure'})\nevent('pipeline_completed')\n",
        "event('pipeline_completed')\nsys.exit(7)\n",
    ],
)
def test_exit_zero_alone_and_completion_with_error_are_not_success(tmp_path, source):
    supervisor = make(tmp_path, source)
    try:
        supervisor.start()
        finish(supervisor)
        assert supervisor.status == "FAILED"
    finally:
        supervisor.close()


def test_cancel_confirmed_after_real_exit_and_late_cancel_is_noop(tmp_path):
    supervisor = make(tmp_path, "event('runtime_started')\ntime.sleep(30)\n")
    try:
        supervisor.start()
        assert supervisor.wait(0.01) is None
        supervisor.request_cancel()
        assert supervisor.status == "CANCELLING"
        assert json.loads((supervisor.run_root / "cancel.request.json").read_text()) == {
            "runId": "fixture-run-id"
        }
        finish(supervisor)
        assert supervisor.status == "CANCELLED" and supervisor.exit_code != 0
        original = (supervisor.run_root / "cancel.request.json").read_bytes()
        supervisor.request_cancel()
        assert (supervisor.run_root / "cancel.request.json").read_bytes() == original
    finally:
        supervisor.close()


def test_finished_completion_preserved_and_no_cancel_file(tmp_path):
    supervisor = make(tmp_path, "event('pipeline_completed')\n")
    try:
        supervisor.start()
        finish(supervisor)
        supervisor.request_cancel()
        assert supervisor.status == "COMPLETED"
        assert not (supervisor.run_root / "cancel.request.json").exists()
    finally:
        supervisor.close()


def test_cooperative_cancel_file_identity_and_terminal_event(tmp_path):
    supervisor = make(
        tmp_path,
        """
from pathlib import Path
event('runtime_started')
request = Path(os.environ['TEST_RUN_ROOT']) / 'cancel.request.json'
while not request.exists():
    time.sleep(.005)
assert json.loads(request.read_text())['runId'] == 'fixture-run-id'
event('pipeline_cancelled')
sys.exit(130)
""",
        environment={"TEST_RUN_ROOT": str(tmp_path / "run 中文")},
    )
    try:
        supervisor.start()
        supervisor.request_cancel()
        events = finish(supervisor)
        assert supervisor.status == "CANCELLED"
        assert any(event.type == "pipeline_cancelled" for event in events)
    finally:
        supervisor.close()


def live_process(pid):
    try:
        os.kill(pid, 0)
        # A reparented zombie no longer executes; the container init may reap later.
        proc = Path(f"/proc/{pid}/stat")
        if proc.exists() and proc.read_text().split()[2] == "Z":
            return False
        return True
    except ProcessLookupError:
        return False


@pytest.mark.skipif(os.name != "posix", reason="POSIX group cleanup; Windows direct-child only")
def test_cancel_kills_only_owned_group_including_term_resistant_grandchild(tmp_path):
    supervisor = make(
        tmp_path,
        """
import subprocess, signal
signal.signal(signal.SIGTERM, signal.SIG_IGN)
child = subprocess.Popen([sys.executable, '-c', 'import signal,time;signal.signal(signal.SIGTERM,signal.SIG_IGN);time.sleep(30)'])
from pathlib import Path
Path('grandchild.pid').write_text(str(child.pid))
event('runtime_started')
time.sleep(30)
""",
    )
    import subprocess

    unrelated = subprocess.Popen([sys.executable, "-c", "import time;time.sleep(30)"])
    try:
        supervisor.start()
        deadline = time.monotonic() + 4
        while not (tmp_path / "grandchild.pid").exists() and time.monotonic() < deadline:
            time.sleep(0.01)
        pid = int((tmp_path / "grandchild.pid").read_text())
        supervisor.request_cancel()
        finish(supervisor)
        assert supervisor.status == "CANCELLED"
        deadline = time.monotonic() + 2
        while live_process(pid) and time.monotonic() < deadline:
            time.sleep(0.01)
        assert not live_process(pid)
        assert unrelated.poll() is None
    finally:
        supervisor.close()
        unrelated.terminate()
        unrelated.wait(timeout=3)


def test_close_active_process_cleans_it_and_spawn_failure_is_recorded(tmp_path):
    supervisor = make(tmp_path, "time.sleep(30)\n")
    supervisor.start()
    supervisor.close()
    assert supervisor.status == "CANCELLED"
    assert supervisor.exit_code is not None
    second = tmp_path / "second"
    second.mkdir()
    broken = ManagedSupervisor(second, "broken", [str(tmp_path / "does-not-exist")], tmp_path)
    try:
        with pytest.raises(FileNotFoundError):
            broken.start()
        assert broken.status == "FAILED"
        assert broken.events()[-1].payload["spawnFailed"] is True
        assert broken.events()[-1].type == "process_spawn_failed"
        assert "exitCode" not in broken.events()[-1].payload
        assert not any(event.type == "process_exited" for event in broken.events())
    finally:
        broken.close()


def test_preexisting_logs_not_overwritten_and_symlink_refused(tmp_path):
    supervisor = make(tmp_path, "event('pipeline_completed')\n")
    logs = supervisor.run_root / "logs"
    logs.mkdir()
    original = logs / "train.log"
    original.write_bytes(b"keep")
    try:
        with pytest.raises(FileExistsError):
            supervisor.start()
        assert original.read_bytes() == b"keep"
    finally:
        supervisor.close()


def test_duplicate_epoch_and_terminal_events_are_protocol_faults(tmp_path):
    supervisor = make(
        tmp_path,
        """
metrics = {'epoch': 1, 'train_loss': .5, 'test_accuracy': .1, 'train_samples': 4, 'test_samples': 2, 'elapsed_seconds': .01}
event('epoch_completed', metrics)
event('epoch_completed', metrics)
event('pipeline_completed')
event('pipeline_completed')
""",
    )
    try:
        supervisor.start()
        events = finish(supervisor)
        assert supervisor.status == "FAILED"
        assert len([event for event in events if event.type == "epoch_completed"]) == 1
        assert len([event for event in events if event.type == "pipeline_completed"]) == 1
    finally:
        supervisor.close()


def test_log_directory_symlink_is_failed_without_outside_write(tmp_path):
    supervisor = make(tmp_path, "event('pipeline_completed')\n")
    outside = tmp_path / "outside"
    outside.mkdir()
    (supervisor.run_root / "logs").symlink_to(outside, target_is_directory=True)
    with pytest.raises(ValueError, match="symlink"):
        supervisor.start()
    assert supervisor.status == "FAILED" and list(outside.iterdir()) == []
    supervisor.close()


def test_recorded_run_is_not_relaunched(tmp_path):
    supervisor = make(tmp_path, "event('pipeline_completed')\n")
    supervisor.start()
    finish(supervisor)
    supervisor.close()
    journal = supervisor.run_root / "logs/runtime-events.jsonl"
    original = journal.read_bytes()
    second = ManagedSupervisor(supervisor.run_root, "fixture-run-id", supervisor.argv, tmp_path)
    try:
        with pytest.raises(ValueError, match="relaunch"):
            second.start()
        assert second.status == "FAILED"
        assert journal.read_bytes() == original
    finally:
        second.close()


def test_reader_start_failure_does_not_leave_child_running(tmp_path, monkeypatch):
    import threading

    supervisor = make(tmp_path, "time.sleep(30)\n")

    def fail_start(self):
        raise RuntimeError("test thread start failure")

    monkeypatch.setattr(threading.Thread, "start", fail_start)
    try:
        with pytest.raises(RuntimeError, match="thread start failure"):
            supervisor.start()
        assert supervisor.status == "FAILED"
        assert supervisor.exit_code is not None
        assert supervisor.events()[-1].payload["managementFailed"] is True
    finally:
        supervisor.close()


def test_foreign_cancel_file_preserved_and_close_still_cleans_process(tmp_path):
    supervisor = make(tmp_path, "time.sleep(30)\n")
    supervisor.start()
    request = supervisor.run_root / "cancel.request.json"
    request.write_bytes(b'{"runId":"other-run"}')
    original = request.read_bytes()
    with pytest.raises(ValueError, match="another run"):
        supervisor.request_cancel()
    assert request.read_bytes() == original
    supervisor.close()
    assert request.read_bytes() == original
    assert supervisor.status == "CANCELLED"


def test_log_fsync_failure_is_a_management_fault_not_completion(tmp_path, monkeypatch):
    original = os.fsync

    def fail_log(fd):
        path = os.readlink(f"/proc/self/fd/{fd}")
        if path.endswith(("train.log", "stderr.log")):
            raise OSError("synthetic log fsync failure")
        return original(fd)

    monkeypatch.setattr(os, "fsync", fail_log)
    supervisor = make(tmp_path, "event('pipeline_completed')\n")
    try:
        supervisor.start()
        events = finish(supervisor)
        assert supervisor.status == "FAILED" and supervisor.exit_code == 0
        assert any(
            event.type == "runtime_error"
            and event.payload.get("message") == "Managed log persistence failed"
            for event in events
        )
    finally:
        supervisor.close()


def test_snapshot_cannot_observe_exit_append_before_terminal_done(tmp_path):
    from concurrent.futures import ThreadPoolExecutor, TimeoutError
    import threading

    supervisor = make(
        tmp_path,
        "from pathlib import Path\nevent('runtime_started')\nwhile not Path('finish-fixture').exists(): time.sleep(.01)\nevent('pipeline_completed')\n",
    )
    appended, release = threading.Event(), threading.Event()
    try:
        supervisor.start()
        append = supervisor._journal.append

        def gated(kind, block, payload):
            result = append(kind, block, payload)
            if kind == "process_exited":
                appended.set()
                assert release.wait(3)
            return result

        supervisor._journal.append = gated
        (tmp_path / "finish-fixture").touch()
        assert appended.wait(2)

        def take_snapshot():
            with supervisor.snapshot() as state:
                return state

        with ThreadPoolExecutor(1) as pool:
            task = pool.submit(take_snapshot)
            with pytest.raises(TimeoutError):
                task.result(0.05)
            release.set()
            assert task.result(2) == ("COMPLETED", True, 0)
    finally:
        release.set()
        supervisor.close()
