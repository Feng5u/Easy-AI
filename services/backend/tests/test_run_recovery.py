"""Crash checkpoints use real persisted journals; no training process is launched."""

import json
import sys
from pathlib import Path

import pytest

from easyai.services.event_journal import EventJournal
from easyai.services.run_service import RunService
from test_run_service import prepare


def checkpoint(owned, finished: bool):
    """Represent a crash after runtime logging but before catalog/SSE refresh."""
    _, service, _, _, _ = owned
    run = prepare(owned)
    root = service.root
    service.close()
    catalog = json.loads((root / "catalog.json").read_bytes())
    catalog["entries"][run.run_id]["run"]["status"] = "RUNNING"
    (root / "catalog.json").write_text(json.dumps(catalog), encoding="utf-8")
    runtime = EventJournal(
        Path(run.config.run_root) / "logs/runtime-events.jsonl", run.run_id, "runtime"
    )
    try:
        runtime.append("runtime_started", "training", {})
        if finished:
            runtime.append("runtime_error", "training", {"message": "stdlib crash fixture"})
            runtime.append("process_exited", None, {"exitCode": 1})
    finally:
        runtime.close()
    return root, run


def test_restart_replays_complete_failed_runtime_journal_and_releases_active_guard(owned):
    root, original = checkpoint(owned, finished=True)
    recovered = RunService(root)
    try:
        run = recovered.get(original.run_id)
        assert run.status == "FAILED"
        events = recovered.events(original.run_id)
        runtime = [event for event in events if event.source == "runtime"]
        assert [event.type for event in runtime] == [
            "runtime_started",
            "runtime_error",
            "process_exited",
        ]
        assert [event.source_seq for event in runtime] == [1, 2, 3]
        assert all(event.run_id == original.run_id for event in events)
        assert [event.seq for event in events] == list(range(1, len(events) + 1))
        # Repeated polling/replay does not duplicate the recovered suffix.
        recovered.get(original.run_id)
        assert recovered.events(original.run_id) == events
        project, _, document, phash, data = owned
        next_run = recovered.prepare(
            project,
            document.revision,
            phash,
            "new-key-after-recovery",
            Path(sys.executable),
            data,
        )
        assert next_run.run_id != original.run_id and next_run.status == "CREATED"
    finally:
        recovered.close()


def test_restart_without_process_exit_keeps_unknown_identity_and_never_relaunches(owned):
    root, original = checkpoint(owned, finished=False)
    recovered = RunService(root)
    try:
        run = recovered.get(original.run_id)
        assert run.status == "RUNNING" and run.connection_state == "disconnected"
        with pytest.raises(ValueError, match="RUN_PROCESS_IDENTITY_UNKNOWN"):
            recovered.cancel(original.run_id)
        with pytest.raises(ValueError, match="RUN_PROCESS_IDENTITY_UNKNOWN"):
            recovered.start(original.run_id)
        project, _, document, phash, data = owned
        with pytest.raises(ValueError, match="RUN_ACTIVE_CONFLICT"):
            recovered.prepare(
                project,
                document.revision,
                phash,
                "new-key-with-unknown-process",
                Path(sys.executable),
                data,
            )
        journal = Path(original.config.run_root) / "logs/runtime-events.jsonl"
        records = [json.loads(line) for line in journal.read_bytes().splitlines()]
        assert [event["type"] for event in records] == ["runtime_started"]
        assert not (Path(original.config.run_root) / "cancel.request.json").exists()
        assert not (Path(original.config.run_root) / "logs/train.log").exists()
    finally:
        recovered.close()
