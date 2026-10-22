"""Application journal fsync is durable even when the catalog checkpoint fails."""

import json
from pathlib import Path

import pytest

from easyai.runtime.supervisor import ManagedSupervisor
from easyai.services.run_service import RunService
from test_run_service import prepare


def test_cancelled_event_survives_catalog_failure_and_cannot_restart(owned, monkeypatch):
    service = owned[1]
    original = prepare(owned)
    root = service.root

    def failed_catalog():
        raise OSError("simulated crash before catalog checkpoint")

    with monkeypatch.context() as patch:
        patch.setattr(service, "_persist", failed_catalog)
        with pytest.raises(OSError, match="simulated crash"):
            service.cancel(original.run_id)
    service.close()  # No supervisor exists; close cannot conceal the interrupted checkpoint.

    catalog = json.loads((root / "catalog.json").read_bytes())
    assert catalog["entries"][original.run_id]["run"]["status"] == "CREATED"
    log = Path(original.config.run_root) / "logs/events.jsonl"
    persisted = [json.loads(line) for line in log.read_bytes().splitlines()]
    assert persisted[-1]["type"] == "status_changed"
    assert persisted[-1]["payload"]["status"] == "CANCELLED"

    def forbid_launch(_supervisor):
        pytest.fail("A durably cancelled run attempted to launch a training process")

    monkeypatch.setattr(ManagedSupervisor, "start", forbid_launch)
    recovered = RunService(root)
    try:
        assert recovered.get(original.run_id).status == "CANCELLED"
        assert recovered.events(original.run_id)[-1].payload["status"] == "CANCELLED"
        with pytest.raises(ValueError, match="RUN_PROCESS_IDENTITY_UNKNOWN"):
            recovered.start(original.run_id)
    finally:
        recovered.close()


@pytest.mark.parametrize("terminal", ["FAILED", "SUCCEEDED"])
def test_durable_terminal_application_event_does_not_regress_to_old_catalog(owned, terminal):
    service = owned[1]
    original = prepare(owned)
    root = service.root
    # This checkpoint represents an already validated local terminal transition:
    # its complete application event reached fsync, but catalog replacement did not.
    service._journal(original.run_id).append("status_changed", None, {"status": terminal})
    service.close()
    catalog = json.loads((root / "catalog.json").read_bytes())
    assert catalog["entries"][original.run_id]["run"]["status"] == "CREATED"
    recovered = RunService(root)
    try:
        assert recovered.get(original.run_id).status == terminal
        events = recovered.events(original.run_id)
        assert events[-1].payload["status"] == terminal
        assert len(events) == 2
    finally:
        recovered.close()
