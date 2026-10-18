"""Exact mkdir -> directory-sync -> first-adoption window, POSIX only."""

from concurrent.futures import ThreadPoolExecutor
import os
import threading

import pytest

from test_run_service import prepare


@pytest.mark.skipif(os.name != "posix", reason="POSIX directory claim window")
@pytest.mark.parametrize("through_prepare", [False, True], ids=["directory", "run-prepare"])
def test_new_child_rejects_same_name_replacement_during_sync(owned, monkeypatch, through_prepare):
    service = owned[1]
    parent = service._store
    entered, release = threading.Event(), threading.Event()
    original_sync = parent.sync

    def paused_sync():
        entered.set()
        assert release.wait(5), "test sync gate timed out"
        original_sync()

    monkeypatch.setattr(parent, "sync", paused_sync)
    with ThreadPoolExecutor(max_workers=1) as pool:
        future = (
            pool.submit(prepare, owned)
            if through_prepare
            else pool.submit(parent.new_child, "fresh")
        )
        try:
            assert entered.wait(5), "mkdir did not reach directory sync"
            children = [path for path in service.root.iterdir() if path.is_dir()]
            assert len(children) == 1
            claimed = children[0]
            before = claimed.stat()
            claimed.rename(service.root / "preserved-claim")
            claimed.mkdir(mode=0o700)
            assert (before.st_dev, before.st_ino) != (claimed.stat().st_dev, claimed.stat().st_ino)
        finally:
            release.set()
        try:
            result = future.result(timeout=5)
        except (ValueError, OSError) as error:
            assert "REPLACED" in str(error)
        else:
            if not through_prepare:
                result.close()
            pytest.fail(
                "Claim adopted the replacement; replacement entries="
                + repr(sorted(path.name for path in claimed.iterdir()))
            )
    assert list(claimed.iterdir()) == []
    assert not service._ledger.entries and not service._supervisors
