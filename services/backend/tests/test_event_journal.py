"""Real filesystem journals and processes; no training environment is involved."""

import os
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import patch

import pytest

from easyai.domain.contracts import Event
from easyai.services.event_journal import MAX_LINE_BYTES, EventJournal, _encoded


def runtime_event(seq: int = 1) -> Event:
    return Event(
        run_id="run-1",
        seq=seq,
        source="runtime",
        source_seq=seq,
        timestamp="2026-10-18T00:00:00+00:00",
        type="progress",
        block_id="training",
        payload={"samples": seq},
    )


def record(event: Event) -> bytes:
    return event.model_dump_json(by_alias=True).encode() + b"\n"


def test_append_fsync_reopen_and_isolated_snapshots(tmp_path: Path) -> None:
    path = tmp_path / "中文 events.jsonl"
    journal = EventJournal(path, "run-1", "runtime")
    payload = {"nested": [1]}
    with patch("easyai.services.event_journal.os.fsync", wraps=os.fsync) as sync:
        first = journal.append("progress", "training", payload)
        assert sync.call_count == 1
    payload["nested"].append(2)
    first.payload["nested"].append(3)
    assert journal.after(0)[0].payload == {"nested": [1]}
    journal.close()
    journal.close()
    with pytest.raises(ValueError, match="JOURNAL_CLOSED"):
        journal.after(0)
    reopened = EventJournal(path, "run-1", "runtime")
    try:
        assert reopened.recovery_info is None
        assert reopened.append("pipeline_completed", "training", {}).seq == 2
        assert [event.source_seq for event in reopened.after(0)] == [1, 2]
        assert [event.seq for event in reopened.after(1)] == [2]
        assert reopened.after(99) == []
    finally:
        reopened.close()


def test_application_deduplication_rebuilt_after_reopen(tmp_path: Path) -> None:
    path = tmp_path / "events.jsonl"
    journal = EventJournal(path, "run-1", "application")
    assert journal.append("status_changed", None, {"state": "STARTING"}).source_seq is None
    incoming = runtime_event()
    received = journal.ingest(incoming)
    assert received is not None and received.seq == 2 and received.source_seq == 1
    assert received.source == "runtime"
    assert journal.ingest(incoming) is None
    journal.close()
    reopened = EventJournal(path, "run-1", "application")
    try:
        size = path.stat().st_size
        assert reopened.ingest(incoming) is None
        assert path.stat().st_size == size
        with pytest.raises(ValueError, match="JOURNAL_SOURCE_CONFLICT"):
            reopened.ingest(incoming.model_copy(update={"payload": {"samples": 9}}))
        with pytest.raises(ValueError, match="JOURNAL_SOURCE_SEQUENCE_INVALID"):
            reopened.ingest(runtime_event(3))
        with pytest.raises(ValueError, match="JOURNAL_SOURCE_OR_RUN_INVALID"):
            reopened.ingest(incoming.model_copy(update={"run_id": "other"}))
        assert reopened.ingest(runtime_event(2)).seq == 3
    finally:
        reopened.close()


@pytest.mark.parametrize("tail", [b'{"half":', b"\xe4\xb8", b"x" * (MAX_LINE_BYTES * 2 + 19)])
def test_only_unfinished_tail_is_truncated(tmp_path: Path, tail: bytes) -> None:
    path = tmp_path / "events.jsonl"
    complete = record(runtime_event())
    path.write_bytes(complete + tail)
    journal = EventJournal(path, "run-1", "runtime")
    try:
        assert path.read_bytes() == complete
        assert journal.recovery_info == {
            "discardedBytes": len(tail),
            "completeBytes": len(complete),
        }
        assert journal.append("progress", "training", {}).seq == 2
    finally:
        journal.close()


@pytest.mark.parametrize(
    "bad",
    [
        b"not-json\n",
        b"\xff\n",
        b"{}\n",
        b' {"seq":1,"seq":2}\n',
        b"x" * MAX_LINE_BYTES + b"\n",
        record(runtime_event(2)),
        record(runtime_event().model_copy(update={"run_id": "other"})),
        record(runtime_event().model_copy(update={"source_seq": 2})),
        record(runtime_event().model_copy(update={"source": "application", "source_seq": None})),
        record(runtime_event().model_copy(update={"type": "invented"})),
    ],
)
def test_complete_invalid_lines_fail_closed_without_repair(tmp_path: Path, bad: bytes) -> None:
    path = tmp_path / "events.jsonl"
    path.write_bytes(bad + b"unfinished")
    with pytest.raises((ValueError, UnicodeDecodeError)):
        EventJournal(path, "run-1", "runtime")
    assert path.read_bytes() == bad + b"unfinished"
    # Failed construction released the process lock, rather than wedging future opens.
    path.write_bytes(record(runtime_event()))
    EventJournal(path, "run-1", "runtime").close()


def test_application_recovery_rejects_source_sequence_gaps(tmp_path: Path) -> None:
    path = tmp_path / "events.jsonl"
    bad = record(runtime_event().model_copy(update={"source_seq": 2}))
    path.write_bytes(bad)
    with pytest.raises(ValueError, match="JOURNAL_SOURCE_SEQUENCE_INVALID"):
        EventJournal(path, "run-1", "application")
    assert path.read_bytes() == bad


def test_schema_metrics_size_limits_and_invalid_cursor_do_not_append(tmp_path: Path) -> None:
    path = tmp_path / "events.jsonl"
    journal = EventJournal(path, "run-1", "runtime")
    try:
        for event_type, payload in [
            ("invented", {}),
            ("epoch_completed", {"epoch": 1}),
            ("progress", {"value": float("nan")}),
            ("progress", {"text": "中" * MAX_LINE_BYTES}),
        ]:
            with pytest.raises(ValueError):
                journal.append(event_type, None, payload)
        assert path.read_bytes() == b""
        for cursor in [-1, True]:
            with pytest.raises(ValueError, match="JOURNAL_CURSOR_INVALID"):
                journal.after(cursor)
        with pytest.raises(ValueError, match="JOURNAL_INGEST_REQUIRES_APPLICATION"):
            journal.ingest(runtime_event())
        assert journal.append("progress", None, {}).seq == 1
    finally:
        journal.close()


def test_threaded_append_keeps_one_contiguous_order(tmp_path: Path) -> None:
    journal = EventJournal(tmp_path / "events.jsonl", "run-1", "runtime")
    try:
        with ThreadPoolExecutor(8) as pool:
            events = list(pool.map(lambda n: journal.append("progress", None, {"n": n}), range(50)))
        assert sorted(event.seq for event in events) == list(range(1, 51))
        assert [event.seq for event in journal.after(0)] == list(range(1, 51))
    finally:
        journal.close()


def test_kernel_writer_lock_survives_owner_crash_without_stale_lock(tmp_path: Path) -> None:
    path = tmp_path / "events.jsonl"
    script = (
        "from pathlib import Path; import sys; "
        "from easyai.services.event_journal import EventJournal; "
        "j=EventJournal(Path(sys.argv[1]), 'run-1', 'runtime'); "
        "j.append('runtime_started', None, {}); print('ready', flush=True); sys.stdin.read()"
    )
    child = subprocess.Popen(
        [sys.executable, "-c", script, str(path)],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    try:
        assert child.stdout is not None and child.stdout.readline() == b"ready\n"
        with pytest.raises(ValueError, match="JOURNAL_WRITER_HELD"):
            EventJournal(path, "run-1", "runtime")
        child.kill()
        child.wait(timeout=5)
        reopened = EventJournal(path, "run-1", "runtime")
        try:
            assert reopened.append("progress", None, {}).seq == 2
        finally:
            reopened.close()
    finally:
        if child.poll() is None:
            child.kill()
            child.wait(timeout=5)
        for stream in (child.stdin, child.stdout, child.stderr):
            if stream is not None:
                stream.close()


def test_symlinks_and_replaced_journal_are_not_written(tmp_path: Path) -> None:
    outside = tmp_path / "outside"
    outside.write_bytes(b"keep")
    link = tmp_path / "link.jsonl"
    link.symlink_to(outside)
    with pytest.raises(ValueError, match="JOURNAL_PATH_FORBIDDEN"):
        EventJournal(link, "run-1", "runtime")
    path = tmp_path / "events.jsonl"
    journal = EventJournal(path, "run-1", "runtime")
    path.unlink()
    path.write_bytes(b"replacement")
    try:
        with pytest.raises(ValueError, match="JOURNAL_PATH_REPLACED"):
            journal.append("progress", None, {})
        assert outside.read_bytes() == b"keep" and path.read_bytes() == b"replacement"
    finally:
        journal.close()


def test_failed_write_requires_reopen_and_recovers_partial_tail(tmp_path: Path) -> None:
    path = tmp_path / "events.jsonl"
    journal = EventJournal(path, "run-1", "runtime")
    original = os.write

    def partial_write(fd: int, data: bytes) -> int:
        original(fd, data[:5])
        raise OSError("simulated interrupted write")

    with patch("easyai.services.event_journal.os.write", side_effect=partial_write):
        with pytest.raises(OSError, match="simulated"):
            journal.append("progress", None, {})
    with pytest.raises(ValueError, match="JOURNAL_WRITE_UNCERTAIN"):
        journal.append("progress", None, {})
    journal.close()
    reopened = EventJournal(path, "run-1", "runtime")
    try:
        assert reopened.recovery_info == {"discardedBytes": 5, "completeBytes": 0}
        assert reopened.append("progress", None, {}).seq == 1
    finally:
        reopened.close()


def test_complete_corruption_after_valid_records_never_truncates(tmp_path: Path) -> None:
    path = tmp_path / "events.jsonl"
    raw = record(runtime_event()) + b"not-json\n" + b"unfinished"
    path.write_bytes(raw)
    with pytest.raises(ValueError):
        EventJournal(path, "run-1", "runtime")
    assert path.read_bytes() == raw


def test_exact_line_byte_budget_includes_newline_and_utf8(tmp_path: Path) -> None:
    path = tmp_path / "events.jsonl"
    journal = EventJournal(path, "run-1", "runtime")
    timestamp = "2026-10-18T00:00:00+00:00"
    blank = runtime_event().model_copy(update={"payload": {"text": ""}})
    spare = MAX_LINE_BYTES - len(_encoded(blank))
    text = "中" * (spare // 3) + "x" * (spare % 3)
    try:
        with patch("easyai.services.event_journal.datetime") as clock:
            clock.now.return_value.isoformat.return_value = timestamp
            journal.append("progress", "training", {"text": text})
            assert path.stat().st_size == MAX_LINE_BYTES
            with pytest.raises(ValueError, match="JOURNAL_LINE_LIMIT"):
                journal.append("progress", "training", {"text": text + "x"})
    finally:
        journal.close()
    reopened = EventJournal(path, "run-1", "runtime")
    try:
        assert len(reopened.after(0)) == 1 and reopened.recovery_info is None
    finally:
        reopened.close()


def test_real_epoch_metrics_keep_fraction_units(tmp_path: Path) -> None:
    journal = EventJournal(tmp_path / "events.jsonl", "run-1", "runtime")
    metrics = dict(
        epoch=1,
        train_loss=0.25,
        test_accuracy=0.973,
        train_samples=8,
        test_samples=4,
        elapsed_seconds=0.5,
    )
    try:
        saved = journal.append("epoch_completed", "training", metrics)
        assert saved.payload["test_accuracy"] == 0.973
        with pytest.raises(ValueError):
            journal.append("epoch_completed", "training", metrics | {"test_accuracy": 97.3})
        assert len(journal.after(0)) == 1
    finally:
        journal.close()


def test_read_only_runtime_replay_does_not_take_writer_or_modify_unfinished_tail(tmp_path):
    from easyai.services.event_journal import read_runtime_events

    path = tmp_path / "runtime-events.jsonl"
    writer = EventJournal(path, "run-test", "runtime")
    try:
        first = writer.append("runtime_started", None, {})
        with path.open("ab") as stream:
            stream.write(b'{"partial":"\xe4')
        before = path.read_bytes()
        assert read_runtime_events(path, "run-test") == [first]
        assert path.read_bytes() == before
    finally:
        writer.close()


@pytest.mark.skipif(os.name != "posix", reason="POSIX FIFO regression")
def test_read_only_runtime_replay_rejects_fifo_without_blocking(tmp_path):
    path = tmp_path / "runtime-events.jsonl"
    os.mkfifo(path)
    script = """
import sys
from pathlib import Path
from easyai.services.event_journal import read_runtime_events
try:
 read_runtime_events(Path(sys.argv[1]), 'fifo-test')
except ValueError as error:
 assert str(error) == 'JOURNAL_PATH_FORBIDDEN'
else:
 raise AssertionError('FIFO accepted')
"""
    result = subprocess.run(
        [sys.executable, "-c", script, str(path)], capture_output=True, text=True, timeout=3
    )
    assert result.returncode == 0, result.stderr
    assert path.is_fifo()
