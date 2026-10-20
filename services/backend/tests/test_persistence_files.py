"""No training: own subprocesses keep hostile local-file regressions bounded."""

import os
import subprocess
import sys

import pytest

from easyai.security.files import read_regular


def test_bounded_regular_read_and_oversized_file(tmp_path):
    path = tmp_path / "large.json"
    path.write_bytes(b"x" * 33)
    with pytest.raises(ValueError, match="FILE_SIZE_LIMIT"):
        read_regular(path, 32)
    assert read_regular(path, 32, prefix=True) == b"x" * 32
    assert read_regular(path, 33) == b"x" * 33


@pytest.mark.skipif(os.name != "posix", reason="POSIX named pipe regression")
@pytest.mark.parametrize(
    "kind, expected",
    [
        ("catalog", "REMOTE_CACHE_FILE_UNSAFE"),
        ("snapshot", "FILE_NOT_REGULAR"),
        ("config", "FILE_NOT_REGULAR"),
        ("bundle", "FILE_NOT_REGULAR"),
    ],
)
def test_persistent_fifo_rejected_without_blocking_owned_store(owned, kind, expected):
    from test_run_service import prepare

    _, service, _, _, _ = owned
    run = prepare(owned)
    root = service.root
    service.close()
    paths = {
        "catalog": root / "catalog.json",
        "snapshot": root / run.run_id / "snapshot/project.easyai.json",
        "config": root / run.run_id / "run-config.json",
        "bundle": root / run.run_id / "bundle.json",
    }
    path = paths[kind]
    path.rename(path.with_name(path.name + ".preserved"))
    os.mkfifo(path)
    script = """
import sys
from pathlib import Path
from easyai.services.run_service import RunService
service=None
try:
 service=RunService(Path(sys.argv[1]))
 service.start(sys.argv[2])
except ValueError as error:
 assert str(error)==sys.argv[3], str(error)
else:
 raise AssertionError('FIFO not rejected')
finally:
 if service: service.close()
"""
    result = subprocess.run(
        [sys.executable, "-c", script, str(root), run.run_id, expected],
        capture_output=True,
        text=True,
        timeout=3,
    )
    assert result.returncode == 0, result.stderr
    assert path.is_fifo()
