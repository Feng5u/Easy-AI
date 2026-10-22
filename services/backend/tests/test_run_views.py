"""Export views use registered IDs and bounded bytes, not arbitrary renderer paths."""

import binascii
import hashlib
import struct
import zlib
from pathlib import Path

import pytest

from easyai.services.run_views import RunViews, read_log
from test_run_service import prepare


def png(width=1, height=1):
    def chunk(kind, data):
        return (
            struct.pack(">I", len(data))
            + kind
            + data
            + struct.pack(">I", binascii.crc32(kind + data) & 0xFFFFFFFF)
        )

    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
        + chunk(b"IDAT", zlib.compress(b"\x00\xff\x00\x00"))
        + chunk(b"IEND", b"")
    )


def register_image(owned, content):
    service = owned[1]
    run = prepare(owned)
    directory = Path(run.config.run_root)
    target = directory / "outputs/figure.png"
    target.parent.mkdir()
    target.write_bytes(content)
    record = dict(
        artifactId="image-id",
        runId=run.run_id,
        kind="figure",
        relativePath="outputs/figure.png",
        mimeType="image/png",
        sizeBytes=len(content),
        sha256=hashlib.sha256(content).hexdigest(),
        producerBlockId="figure",
        contributorBlockIds=[],
        syncState="ready",
    )
    service._journal(run.run_id).append("artifact_created", "figure", record)
    # Simulate the ordinary materialized view that RunService builds from its journal.
    service._write_views(run.run_id, service.events(run.run_id))
    return run, target


def test_source_uses_old_snapshot_and_rejects_tampering(owned):
    project, service, document, _, _ = owned
    run = prepare(owned)
    views = RunViews(service)
    first = views.source(run.run_id)
    project.save(document.model_copy(update={"name": "new project edit"}), document.revision)
    assert views.source(run.run_id) == first
    assert first.project_revision == document.revision
    code = Path(run.config.run_root) / "code/train.py"
    code.write_bytes(code.read_bytes() + b"\n# changed")
    with pytest.raises(ValueError, match="HASH_CONFLICT"):
        views.source(run.run_id)


def test_utf8_cursor_waits_for_incomplete_character_and_limits_each_read(tmp_path):
    path = tmp_path / "stdout.log"
    encoded = "中文".encode()
    path.write_bytes(encoded[:2])
    assert read_log(path, 0, False) == ("", 0)
    with path.open("ab") as stream:
        stream.write(encoded[2:])
    assert read_log(path, 0, False) == ("中文", 6)
    path.write_bytes(b"x" * 100000)
    text, cursor = read_log(path, 0, False)
    assert len(text) == cursor == 32768
    with pytest.raises(ValueError, match="CURSOR_INVALID"):
        read_log(path, 100001, False)


def test_registered_png_returns_exact_bytes_and_mismatch_or_escape_is_rejected(owned, tmp_path):
    content = png()
    run, target = register_image(owned, content)
    views = RunViews(owned[1])
    assert views.image(run.run_id, "image-id") == content
    assert len(views.artifacts(run.run_id)) == 1
    with pytest.raises(KeyError):
        views.image(run.run_id, "../../arbitrary-file")
    target.write_bytes(content + b"tampered")
    with pytest.raises(ValueError, match="HASH_CONFLICT"):
        views.image(run.run_id, "image-id")
    target.unlink()
    outside = tmp_path / "outside.png"
    outside.write_bytes(content)
    target.symlink_to(outside)
    with pytest.raises(ValueError, match="FORBIDDEN"):
        views.image(run.run_id, "image-id")


@pytest.mark.parametrize("content", [b"not png", png(9000, 1), png()[:-4]])
def test_registered_invalid_or_oversized_dimension_png_is_rejected(owned, content):
    run, _ = register_image(owned, content)
    with pytest.raises(ValueError, match="PNG_"):
        RunViews(owned[1]).image(run.run_id, "image-id")


def test_missing_logs_are_empty_and_run_parent_symlink_is_rejected(owned, tmp_path):
    service = owned[1]
    run = prepare(owned)
    views = RunViews(service)
    logs = views.logs(run.run_id)
    assert logs.stdout == logs.stderr == "" and logs.stdout_after == logs.stderr_after == 0
    code = Path(run.config.run_root) / "code"
    code.rename(code.with_name("code-preserved"))
    outside = tmp_path / "outside"
    outside.mkdir()
    code.symlink_to(outside, target_is_directory=True)
    with pytest.raises(ValueError, match="FORBIDDEN"):
        views.source(run.run_id)


def test_terminal_logs_done_waits_until_all_pages_and_utf8_tail_are_read(owned):
    from easyai.services.run_views import LOG_CHUNK

    service = owned[1]
    run = prepare(owned)
    directory = Path(run.config.run_root)
    out = "x" * (3 * LOG_CHUNK - 1) + "中文 tail"
    err = "e" * (2 * LOG_CHUNK + 15)
    (directory / "logs/train.log").write_bytes(out.encode())
    (directory / "logs/stderr.log").write_bytes(err.encode())
    service.cancel(run.run_id)
    views = RunViews(service)
    stdout_after = stderr_after = 0
    stdout, stderr = [], []
    pages = 0
    while True:
        page = views.logs(run.run_id, stdout_after, stderr_after)
        pages += 1
        stdout.append(page.stdout)
        stderr.append(page.stderr)
        assert len(page.stdout.encode()) + len(page.stderr.encode()) <= 65536
        stdout_after, stderr_after = page.stdout_after, page.stderr_after
        if page.done:
            break
        assert pages < 10
    assert pages == 4
    assert "".join(stdout) == out and "".join(stderr) == err
    assert stdout_after == len(out.encode()) and stderr_after == len(err.encode())
