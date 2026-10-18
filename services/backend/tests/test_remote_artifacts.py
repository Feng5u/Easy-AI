"""Local SFTP-API fixtures only: no sockets, credentials, torch or remote execution."""

from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
import os
from pathlib import Path
import socket
import struct
import threading
import time
from uuid import uuid4
import zlib

import pytest

from easyai.domain.contracts import Event
from easyai.domain.remote_run import RemoteRunCheckpoint, RemoteRunObservation
from easyai.services.environment_transport import (
    EnvironmentFailure,
    ReadOnlyCommand,
    SshProbeTransport,
)
from easyai.domain.environment import EnvironmentScope
from easyai.services.remote_artifacts import ArtifactFailure, ArtifactSnapshot, SftpArtifactSync
from test_portable_owner import Bundle


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def png():
    def chunk(kind, data):
        return (
            struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data))
        )

    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0))
        + chunk(b"IDAT", zlib.compress(b"\0\0\0\0"))
        + chunk(b"IEND", b"")
    )


class File:
    def __init__(self, path, owner):
        self.stream, self.owner = path.open("rb"), owner

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.stream.close()

    def stat(self):
        return os.fstat(self.stream.fileno())

    def read(self, count):
        assert 0 < count <= 65536
        self.owner.reads.append(count)
        self.owner.before_read(self.stream.name)
        return self.stream.read(count)


class LocalSftp:
    def __init__(self):
        self.reads = []
        self.before_read = lambda path: None
        self.close_error = False
        self.opened = []

    def lstat(self, path):
        return Path(path).lstat()

    def open(self, path, mode, *, bufsize):
        assert mode == "rb" and bufsize == 0
        self.opened.append(path)
        return File(Path(path), self)

    def close(self):
        if self.close_error:
            raise OSError("synthetic close failure")


class Channel:
    def __init__(self):
        self.timeout = None
        self.subsystem = None
        self.closed = False

    def settimeout(self, value):
        self.timeout = value

    def invoke_subsystem(self, value):
        assert self.timeout is not None and value == "sftp"
        self.subsystem = value

    def close(self):
        self.closed = True


class Session:
    def __init__(self, identity):
        self.endpoint, self.host_fingerprint = identity.endpoint, identity.host_fingerprint
        self.io_lock = threading.Lock()
        self.channel = Channel()
        self.closed = False
        self.close_failed = False

    def validate_probe_session(self):
        if self.closed:
            raise ValueError("closed")

    def open_probe_channel(self, timeout):
        self.validate_probe_session()
        return self.channel

    @property
    def closed_quiescent(self):
        return self.closed and not self.close_failed and not self.io_lock.locked()

    def close(self):
        self.closed = True


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    monkeypatch.setattr(
        socket, "create_connection", lambda *a, **k: pytest.fail("No network in artifact fixtures")
    )


class Case:
    def __init__(self, tmp_path):
        self.bundle = Bundle(tmp_path)
        self.root, self.identity = self.bundle.root, self.bundle.identity
        self.cache = tmp_path / "artifact-cache"
        self.cache.mkdir(mode=0o700)
        self.source_map = (self.root / "code/source-map.json").read_bytes()
        self.bundle_manifest = (self.root / "bundle.json").read_bytes()
        block = json.loads(self.source_map)[0]["origin"]["blockId"]
        self.raw = png()
        self.record = dict(
            artifactId=str(uuid4()),
            runId=self.identity.run_id,
            kind="figure",
            relativePath="outputs/中文 图.png",
            mimeType="image/png",
            sizeBytes=len(self.raw),
            sha256=digest(self.raw),
            producerBlockId=block,
            contributorBlockIds=[block],
            phase="before",
            syncState="ready",
        )
        self.events = []
        for kind, payload in (
            ("artifact_created", self.record),
            ("pipeline_completed", {}),
            ("process_exited", {"exitCode": 0}),
        ):
            seq = len(self.events) + 1
            self.events.append(
                Event(
                    run_id=self.identity.run_id,
                    seq=seq,
                    source="runtime",
                    source_seq=seq,
                    timestamp="fixture",
                    type=kind,
                    payload=payload,
                    block_id=block if kind == "artifact_created" else None,
                )
            )
        stream = dict(generation=str(uuid4()), sizeBytes=0, sha256=digest(b""))
        self.observation = RemoteRunObservation(
            identity=self.identity,
            heartbeat=1,
            state="COMPLETED",
            sealed=True,
            exit_code=0,
            streams={key: stream for key in ("events", "stdout", "stderr")},
        )
        self.checkpoint = RemoteRunCheckpoint(
            identity=self.identity,
            start_outcome="acknowledged",
            execution_state="COMPLETED",
            last_observation=self.observation,
        )
        (self.root / "outputs").mkdir(mode=0o700)
        (self.root / self.record["relativePath"]).write_bytes(self.raw)
        self.manifest = dict(
            protocolVersion=1,
            identity=self.identity.model_dump(mode="json", by_alias=True),
            uid=os.geteuid(),
            sourceSeq=3,
            eventsSha256=self.observation.streams.events.sha256,
            artifacts=[self.record],
        )
        self.write_records()
        self.session, self.sftp = Session(self.identity), LocalSftp()
        self.valid = True
        self.mutex = threading.RLock()
        self.service = SftpArtifactSync(
            self.session, self.identity, self.mutex, self.guard, lambda channel: self.sftp
        )

    def guard(self):
        self.session.validate_probe_session()
        if not self.valid:
            raise ValueError("expired fixture lease")

    def write_records(self):
        (self.root / "owner-status.json").write_text(
            self.observation.model_dump_json(by_alias=True)
        )
        (self.root / "remote-artifacts.json").write_text(json.dumps(self.manifest))

    def snapshot(self):
        return ArtifactSnapshot.verified(
            self.checkpoint,
            self.events,
            self.bundle_manifest,
            self.source_map,
            self.observation.artifact_receipt.events_sha256
            if self.observation.artifact_receipt
            else None,
        )

    def sync(self, cancel=None, seconds=2):
        return self.service.sync(
            self.snapshot(), self.cache, cancel or threading.Event(), seconds=seconds
        )


@pytest.fixture
def case(tmp_path):
    return Case(tmp_path)


def test_atomic_verified_download_and_id_lookup(case):
    ready = case.sync()
    assert len(ready) == 1 and ready[0].sync_state == "ready"
    assert (
        SftpArtifactSync.read_ready(case.cache, case.identity, case.record["artifactId"])
        == case.raw
    )
    assert not list(case.cache.glob(".artifact-part-*"))
    assert case.session.channel.closed and case.sftp.reads
    assert case.checkpoint.artifacts_verified is False
    blob = case.cache / ("blob-" + case.record["sha256"])
    blob.write_bytes(b"changed")
    with pytest.raises(ArtifactFailure):
        SftpArtifactSync.read_ready(case.cache, case.identity, case.record["artifactId"])


@pytest.mark.parametrize(
    "field,value",
    [
        ("relativePath", "outputs/../teacher"),
        ("relativePath", "/etc/passwd"),
        ("relativePath", "outputs/a\\b.png"),
        ("relativePath", "outputs//a.png"),
        ("relativePath", "outputs/./a.png"),
        ("relativePath", "outputs/C:a.png"),
        ("relativePath", "code/train.py"),
        ("relativePath", "outputs/a.html"),
        ("mimeType", "text/html"),
        ("producerBlockId", "unknown"),
        ("contributorBlockIds", ["unknown"]),
        ("sizeBytes", 101 * 1024 * 1024),
    ],
)
def test_snapshot_rejects_unsafe_records(case, field, value):
    case.events[0].payload[field] = value
    with pytest.raises(ValueError):
        case.snapshot()
    assert not case.sftp.opened


@pytest.mark.parametrize(
    "mutation", ["duplicate_id", "duplicate_path", "source_gap", "source_map", "bundle", "unsealed"]
)
def test_snapshot_requires_frozen_complete_provenance(case, mutation):
    if mutation.startswith("duplicate"):
        copy = case.events[0].model_copy(deep=True)
        copy.source_seq = 2
        if mutation == "duplicate_path":
            copy.payload["artifactId"] = str(uuid4())
        case.events = [case.events[0], copy] + [
            event.model_copy(update={"source_seq": event.source_seq + 1})
            for event in case.events[1:]
        ]
    elif mutation == "source_gap":
        case.events[0].source_seq = 2
    elif mutation == "source_map":
        case.source_map += b" "
    elif mutation == "bundle":
        value = json.loads(case.bundle_manifest)
        value["files"]["code/train.py"] = "0" * 64
        case.bundle_manifest = json.dumps(value).encode()
    else:
        case.observation.sealed = False
    with pytest.raises(ValueError):
        case.snapshot()


@pytest.mark.parametrize(
    "mutation",
    ["omitted", "added", "identity", "uid", "source", "hash", "oversize", "duplicate_key"],
)
def test_manifest_refuses_untrusted_claims(case, mutation):
    if mutation == "omitted":
        case.manifest["artifacts"] = []
    elif mutation == "added":
        case.manifest["artifacts"].append(dict(case.record))
    elif mutation == "identity":
        case.manifest["identity"]["launchId"] = str(uuid4())
    elif mutation == "uid":
        case.manifest["uid"] += 1
    elif mutation == "source":
        case.manifest["sourceSeq"] += 1
    elif mutation == "hash":
        case.manifest["eventsSha256"] = "f" * 64
    case.write_records()
    path = case.root / "remote-artifacts.json"
    if mutation == "oversize":
        path.write_bytes(b" " * 65537)
    elif mutation == "duplicate_key":
        path.write_text('{"uid":1,"uid":2}')
    with pytest.raises(ArtifactFailure):
        case.sync()
    assert not (case.cache / "artifact-index.json").exists()


@pytest.mark.parametrize(
    "mutation", ["symlink_file", "symlink_dir", "writable_file", "fifo", "hash", "truncated_png"]
)
def test_remote_file_validation_never_publishes_rejected_artifact(case, mutation):
    path = case.root / case.record["relativePath"]
    if mutation == "symlink_file":
        path.unlink()
        path.symlink_to(case.root / "run-config.json")
    elif mutation == "symlink_dir":
        path.unlink()
        path.parent.rmdir()
        path.parent.symlink_to(case.root / "code", target_is_directory=True)
    elif mutation == "writable_file":
        path.chmod(0o666)
    elif mutation == "fifo":
        path.unlink()
        os.mkfifo(path)
    elif mutation == "hash":
        path.write_bytes(b"x" * len(case.raw))
    else:
        raw = case.raw[:-3]
        path.write_bytes(raw)
        case.events[0].payload["sizeBytes"] = len(raw)
        case.events[0].payload["sha256"] = digest(raw)
        case.manifest["artifacts"] = [case.events[0].payload]
        case.write_records()
    with pytest.raises(ArtifactFailure):
        case.sync()
    assert not (case.cache / "artifact-index.json").exists()
    assert not list(case.cache.glob(".artifact-part-*"))


def test_close_failure_cannot_publish_ready(case):
    case.sftp.close_error = True
    with pytest.raises(ArtifactFailure):
        case.sync()
    assert not (case.cache / "artifact-index.json").exists()
    assert case.session.closed


def test_foreign_identity_cache_not_overwritten(case):
    foreign = case.identity.model_copy(update={"launch_id": str(uuid4())})
    raw = json.dumps(
        dict(identity=foreign.model_dump(mode="json", by_alias=True), artifacts=[])
    ).encode()
    index = case.cache / "artifact-index.json"
    index.write_bytes(raw)
    with pytest.raises(ArtifactFailure):
        case.sync()
    assert index.read_bytes() == raw


@pytest.mark.parametrize("action", ["cancel", "expire", "timeout"])
def test_stalled_worker_retains_physical_gate_and_no_late_ready(case, action):
    entered, release, cancel = threading.Event(), threading.Event(), threading.Event()

    def before_read(path):
        if str(path).endswith(".png"):
            entered.set()
            assert release.wait(3)

    case.sftp.before_read = before_read
    scope = EnvironmentScope(
        project_id=case.identity.project_id,
        connection_id=str(uuid4()),
        endpoint=case.identity.endpoint,
        host_fingerprint=case.identity.host_fingerprint,
    )
    environment = SshProbeTransport(scope, case.session)
    with ThreadPoolExecutor(max_workers=1) as executor:
        operation = executor.submit(case.sync, cancel, 0.15 if action == "timeout" else 2)
        assert entered.wait(1)
        if action == "cancel":
            cancel.set()
        elif action == "expire":
            with case.mutex:
                case.valid = False
        if action in ("cancel", "timeout"):
            with pytest.raises(ArtifactFailure, match="CLEANUP_UNCONFIRMED"):
                operation.result(1)
        assert case.session.io_lock.locked()
        assert not environment.quiescent
        with pytest.raises(EnvironmentFailure, match="BUSY"):
            environment.execute(ReadOnlyCommand(("/usr/bin/true",)), threading.Event())
        with pytest.raises(ArtifactFailure, match="BUSY"):
            case.sync()
        assert not (case.cache / "artifact-index.json").exists()
        release.set()
        if action == "expire":
            with pytest.raises(ArtifactFailure):
                operation.result(1)
    deadline = time.monotonic() + 1
    while case.session.io_lock.locked() and time.monotonic() < deadline:
        time.sleep(0.005)
    assert not case.session.io_lock.locked()
    assert not (case.cache / "artifact-index.json").exists()


def test_large_frozen_source_map_remains_legal(case):
    spans = json.loads(case.source_map)
    case.source_map = json.dumps(spans * 5).encode()
    assert 65536 < len(case.source_map) < 8 * 1024 * 1024
    bundle = json.loads(case.bundle_manifest)
    bundle["files"]["code/source-map.json"] = digest(case.source_map)
    bundle["bundleHash"] = digest(
        json.dumps(bundle["files"], sort_keys=True, separators=(",", ":")).encode()
    )
    case.bundle_manifest = json.dumps(bundle).encode()
    case.checkpoint.identity = case.identity.model_copy(
        update={"bundle_hash": bundle["bundleHash"]}
    )
    case.observation.identity = case.checkpoint.identity
    assert case.snapshot().records[0].artifact_id == case.record["artifactId"]


def test_model_raw_bytes_streamed_and_never_deserialized(case):
    raw = b"\x80\x04untrusted pickle bytes; never execute" * 3000
    path = case.root / "outputs/weights.pth"
    path.write_bytes(raw)
    record = case.events[0].payload
    record.update(
        kind="model",
        mimeType="application/octet-stream",
        relativePath="outputs/weights.pth",
        sizeBytes=len(raw),
        sha256=digest(raw),
    )
    case.manifest["artifacts"] = [record]
    case.write_records()
    assert case.sync()[0].sync_state == "ready"
    assert SftpArtifactSync.read_ready(case.cache, case.identity, record["artifactId"]) == raw
    assert case.sftp.reads.count(65536) >= 2


def test_cache_symlink_and_unknown_lock_preserved(case, tmp_path):
    target = tmp_path / "unknown"
    target.write_text("preserve")
    lock = case.cache / ".artifact-writer.lock"
    lock.symlink_to(target)
    with pytest.raises(ArtifactFailure):
        case.sync()
    assert lock.is_symlink() and target.read_text() == "preserve"
    assert not (case.cache / "artifact-index.json").exists()


def test_owner_coordinator_and_sftp_api_fixture_compose(tmp_path):
    """Real detached stdlib child + real coordinator + local SFTP API fixture, no training."""
    from easyai.runners.ssh import RemoteProtocolError, SshRunCoordinator
    from test_portable_owner import LocalCliTransport
    from test_ssh_run_coordinator import auth_for

    # The fixture creates a structural PNG, not a scientific result or fake curve.
    source = r"""
import argparse, base64, hashlib, json, pathlib, time, uuid
from easyai_runtime import emit_event
parser = argparse.ArgumentParser()
parser.add_argument("--config", required=True)
config = json.loads(pathlib.Path(parser.parse_args().config).read_bytes())
root = pathlib.Path(config["runRoot"])
source_map = json.loads((root / "code/source-map.json").read_bytes())
block = source_map[0]["origin"]["blockId"]
(root / "outputs").mkdir(mode=0o700)
raw = base64.b64decode("PNG_FIXTURE")
(root / "outputs/fixture.png").write_bytes(raw)
emit_event("runtime_started", None, {})
emit_event("artifact_created", block, {"artifactId":str(uuid.uuid4()), "runId":config["runId"], "kind":"figure", "relativePath":"outputs/fixture.png", "mimeType":"image/png", "sizeBytes":len(raw), "sha256":hashlib.sha256(raw).hexdigest(), "producerBlockId":block, "contributorBlockIds":[block], "syncState":"ready"})
emit_event("pipeline_completed", None, {})
"""
    import base64

    bundle = Bundle(
        tmp_path, source=source.replace("PNG_FIXTURE", base64.b64encode(png()).decode())
    )
    cache = tmp_path / "download-cache"
    cache.mkdir(mode=0o700)
    (tmp_path / "coordinator").mkdir(mode=0o700)
    coordinator = SshRunCoordinator(tmp_path / "coordinator", bundle.identity)
    try:
        transport = LocalCliTransport(bundle)
        transport.lose_ack = True
        coordinator.attach(bundle.auth, transport, lambda: bundle.auth)
        with pytest.raises(RemoteProtocolError, match="STATE_UNKNOWN"):
            coordinator.start()
        bundle.wait(terminal=True)
        auth = auth_for(bundle.identity)
        resumed = LocalCliTransport(bundle)
        coordinator.attach(auth, resumed, lambda: auth)
        checkpoint = coordinator.poll()
        assert transport.start_calls == 1 and resumed.start_calls == 0
        assert checkpoint.execution_state == "COMPLETED"
        snapshot = coordinator.artifact_snapshot(
            (bundle.root / "bundle.json").read_bytes(),
            (bundle.root / "code/source-map.json").read_bytes(),
        )
        manifest = json.loads((bundle.root / "remote-artifacts.json").read_bytes())
        assert manifest["sourceSeq"] == 4 and manifest["uid"] == os.geteuid()
        assert manifest["eventsSha256"] == checkpoint.last_observation.streams.events.sha256
        session, sftp = Session(bundle.identity), LocalSftp()
        service = SftpArtifactSync(
            session,
            bundle.identity,
            threading.RLock(),
            session.validate_probe_session,
            lambda channel: sftp,
        )
        ready = service.sync(snapshot, cache, threading.Event(), seconds=2)
        assert len(ready) == 1
        assert SftpArtifactSync.read_ready(cache, bundle.identity, ready[0].artifact_id) == png()
        assert coordinator.checkpoint().artifacts_verified is False
        before = (bundle.root / "owner-status.json").read_bytes()
        assert bundle.cli("inspect")["sealed"] is True
        assert (bundle.root / "owner-status.json").read_bytes() == before
    finally:
        coordinator.close()
        bundle.cleanup()


def test_cancellation_after_commit_boundary_preserves_success(case, monkeypatch):
    original = os.replace
    cancel = threading.Event()

    def replace(source, target, **kwargs):
        if target == "artifact-index.json":
            # Final shared-mutex guard already passed. The verified commit wins.
            cancel.set()
        return original(source, target, **kwargs)

    monkeypatch.setattr(os, "replace", replace)
    ready = case.sync(cancel)
    assert ready[0].sync_state == "ready" and cancel.is_set()
    assert SftpArtifactSync.read_ready(case.cache, case.identity, ready[0].artifact_id) == case.raw


def test_ready_lookup_rejects_self_consistent_index_substitution_against_frozen_event(tmp_path):
    from easyai.domain.contracts import ArtifactRecord

    case = Case(tmp_path)
    ready = case.sync()
    expected = ArtifactRecord.model_validate(case.record)
    index_path = case.cache / "artifact-index.json"
    index = json.loads(index_path.read_bytes())
    # A mutable cache index is not authority even if its replacement blob hashes correctly.
    index["artifacts"][0]["phase"] = "after"
    index_path.write_text(json.dumps(index))
    with pytest.raises(ArtifactFailure):
        SftpArtifactSync.read_ready(case.cache, case.identity, ready[0].artifact_id, expected)


def running_receipt(case):
    """Synthetic immutable receipt; the real coordinator-prefix proof has its own integration test."""
    from easyai.domain.remote_run import ArtifactReceipt

    case.events = [event for event in case.events if event.type == "artifact_created"]
    raw_events = b"".join(
        event.model_dump_json(by_alias=True).encode() + b"\n" for event in case.events
    )
    case.observation = case.observation.model_copy(
        update={
            "sealed": False,
            "exit_code": None,
            "state": "RUNNING",
            "streams": case.observation.streams.model_copy(
                update={
                    "events": case.observation.streams.events.model_copy(
                        update={"size_bytes": len(raw_events), "sha256": digest(raw_events)}
                    )
                }
            ),
        },
        deep=True,
    )
    case.manifest.update(
        sourceSeq=len(case.events),
        eventsSha256=digest(raw_events),
        artifacts=[event.payload for event in case.events],
    )
    raw = json.dumps(case.manifest).encode()
    receipt = ArtifactReceipt(
        sha256=digest(raw), source_seq=len(case.events), events_sha256=digest(raw_events)
    )
    case.observation.artifact_receipt = receipt
    case.checkpoint = case.checkpoint.model_copy(
        update={"execution_state": "RUNNING", "last_observation": case.observation}
    )
    case.write_records()
    (case.root / ("remote-artifacts-" + receipt.sha256 + ".json")).write_bytes(raw)
    return case.snapshot()


def add_figure(case, suffix):
    record = dict(case.record, artifactId=str(uuid4()), relativePath="outputs/" + suffix + ".png")
    (case.root / record["relativePath"]).write_bytes(case.raw)
    event = case.events[0].model_copy(
        update={"seq": len(case.events) + 1, "source_seq": len(case.events) + 1, "payload": record},
        deep=True,
    )
    case.events.append(event)
    return record


def test_running_receipts_incremental_hash_dedup_and_real_byte_progress(case):
    snapshot = running_receipt(case)
    progress = []
    ready = case.service.sync(
        snapshot, case.cache, threading.Event(), progress=lambda *v: progress.append(v)
    )
    assert ready[0].sync_state == "ready" and not case.observation.sealed
    assert progress[-1] == (len(case.raw), len(case.raw), len(case.raw))
    assert case.checkpoint.artifacts_verified is False
    first_reads = case.sftp.opened.count(str(case.root / case.record["relativePath"]))
    second = add_figure(case, "epoch2")
    newer = running_receipt(case)
    case.session.channel = Channel()
    ready = case.service.sync(
        newer, case.cache, threading.Event(), progress=lambda *v: progress.append(v)
    )
    assert len(ready) == 2 and progress[-1] == (0, 2 * len(case.raw), 2 * len(case.raw))
    assert case.sftp.opened.count(str(case.root / case.record["relativePath"])) == first_reads
    # Same hash deduplicates both per-run artifacts without reading the second remote file.
    assert str(case.root / second["relativePath"]) not in case.sftp.opened
    assert SftpArtifactSync.read_ready(case.cache, case.identity, second["artifactId"]) == case.raw
    index = (case.cache / "artifact-index.json").read_bytes()
    case.session.channel = Channel()
    with pytest.raises(ArtifactFailure):
        case.service.sync(snapshot, case.cache, threading.Event())
    assert (case.cache / "artifact-index.json").read_bytes() == index


def test_running_model_is_registered_but_not_downloaded(case):
    record = case.events[0].payload
    record.update(
        kind="model", mimeType="application/octet-stream", relativePath="outputs/model.pth"
    )
    snapshot = running_receipt(case)
    assert case.service.sync(snapshot, case.cache, threading.Event()) == []
    assert not any(path.endswith("model.pth") for path in case.sftp.opened)


def test_new_incomplete_file_never_replaces_previous_verified_index(case):
    running_receipt(case)
    case.sync()
    index = (case.cache / "artifact-index.json").read_bytes()
    record = add_figure(case, "incomplete")
    record.update(sha256=digest(case.raw + b"different"), sizeBytes=len(case.raw) + 9)
    snapshot = running_receipt(case)
    case.session.channel = Channel()
    with pytest.raises(ArtifactFailure):
        case.service.sync(snapshot, case.cache, threading.Event())
    assert (case.cache / "artifact-index.json").read_bytes() == index
    assert (
        SftpArtifactSync.read_ready(case.cache, case.identity, case.record["artifactId"])
        == case.raw
    )
    assert not list(case.cache.glob(".artifact-part-*"))


def test_running_receipt_requires_exact_committed_prefix_and_immutable_digest(case):
    snapshot = running_receipt(case)
    with pytest.raises(ArtifactFailure):
        ArtifactSnapshot.verified(
            case.checkpoint, case.events, case.bundle_manifest, case.source_map, "0" * 64
        )
    path = case.root / ("remote-artifacts-" + case.observation.artifact_receipt.sha256 + ".json")
    path.write_bytes(path.read_bytes() + b" ")
    with pytest.raises(ArtifactFailure):
        case.service.sync(snapshot, case.cache, threading.Event())
    assert not (case.cache / "artifact-index.json").exists()


def test_newer_owner_status_cannot_expand_frozen_receipt_reads(case):
    snapshot = running_receipt(case)
    later = add_figure(case, "not-in-committed-snapshot")
    running_receipt(case)
    ready = case.service.sync(snapshot, case.cache, threading.Event())
    assert [item.artifact_id for item in ready] == [case.record["artifactId"]]
    assert str(case.root / later["relativePath"]) not in case.sftp.opened
    assert not case.checkpoint.artifacts_verified


def test_live_snapshot_never_re_reads_mutable_heartbeat_for_artifact_authority(case):
    snapshot = running_receipt(case)

    def racing_heartbeat(path):
        if str(path).endswith("owner-status.json"):
            pytest.fail(
                "Live downloads must use the committed receipt, not race a mutable heartbeat"
            )

    case.sftp.before_read = racing_heartbeat
    assert case.service.sync(snapshot, case.cache, threading.Event())[0].sync_state == "ready"
    assert not any(path.endswith("owner-status.json") for path in case.sftp.opened)


def test_cancel_interrupt_worker_must_retire_before_gate_release(case):
    entered, read_release, close_entered, close_release = (threading.Event() for _ in range(4))
    cancel = threading.Event()
    original_close = case.session.channel.close

    def blocked_close():
        if threading.current_thread().name == "easyai-artifact-interrupt":
            close_entered.set()
            assert close_release.wait(3)
        original_close()

    def blocked_read(path):
        if str(path).endswith(".png"):
            entered.set()
            assert read_release.wait(3)

    case.session.channel.close = blocked_close
    case.sftp.before_read = blocked_read
    with ThreadPoolExecutor(max_workers=1) as executor:
        operation = executor.submit(case.sync, cancel)
        try:
            assert entered.wait(1)
            cancel.set()
            assert close_entered.wait(1)
            with pytest.raises(ArtifactFailure, match="CLEANUP_UNCONFIRMED") as caught:
                operation.result(1)
            assert caught.value.failure.code == "SYNC_CANCELLED"
            assert caught.value.cleanup_failure.model_dump() == {
                "stage": "watcher_cleanup",
                "code": "SYNC_CLEANUP_UNCONFIRMED",
            }
            read_release.set()
            # The data worker can close its channel, but its interrupt owner is still blocked.
            assert not case.service.quiescent and case.session.io_lock.locked()
            assert not (case.cache / "artifact-index.json").exists()
        finally:
            read_release.set()
            close_release.set()
    case.service._worker.join(2)
    assert case.service.quiescent and not case.session.io_lock.locked()


@pytest.mark.parametrize(
    "fault,stage,code",
    [
        ("receipt_read", "receipt_read", "SYNC_IO_FAILED"),
        ("receipt_digest", "receipt_digest", "SYNC_INVALID_EVIDENCE"),
        ("receipt_records", "receipt_records", "SYNC_INVALID_EVIDENCE"),
        ("artifact_read", "artifact_read", "SYNC_IO_FAILED"),
        ("cache_commit", "cache_commit", "SYNC_IO_FAILED"),
        ("channel_cleanup", "channel_cleanup", "SYNC_IO_FAILED"),
        ("cache_cleanup", "cache_cleanup", "SYNC_IO_FAILED"),
        ("vendor_prefix", "receipt_read", "SYNC_UNKNOWN"),
    ],
)
def test_fixed_sync_failure_stages_never_include_external_exception_text(
    case, monkeypatch, fault, stage, code
):
    from easyai.security.remote_cache import _PosixDirectory as LocalDirectory
    from easyai.domain.remote_run import ArtifactReceipt

    snapshot = running_receipt(case)
    secret = "SYNC_IO_FAILED PASSWORD_SENTINEL /private/server/file"
    if fault == "receipt_digest":
        path = case.root / (
            "remote-artifacts-" + case.observation.artifact_receipt.sha256 + ".json"
        )
        path.write_bytes(path.read_bytes() + b" ")
    elif fault == "receipt_records":
        manifest = dict(case.manifest, artifacts=[dict(case.record, phase="after")])
        raw = json.dumps(manifest).encode()
        receipt = case.observation.artifact_receipt.model_copy(update={"sha256": digest(raw)})
        case.observation.artifact_receipt = ArtifactReceipt.model_validate(receipt.model_dump())
        (case.root / ("remote-artifacts-" + receipt.sha256 + ".json")).write_bytes(raw)
        snapshot = case.snapshot()
    elif fault == "cache_commit":
        original = LocalDirectory.publish

        def publish(self, name, destination, **kwargs):
            if destination == "artifact-index.json":
                raise OSError(secret)
            return original(self, name, destination, **kwargs)

        monkeypatch.setattr(LocalDirectory, "publish", publish)
    elif fault == "channel_cleanup":
        case.sftp.close_error = True
    elif fault == "cache_cleanup":
        from easyai.services.remote_artifacts import _Cache

        original_close = _Cache.close

        def fail_cache_close(self):
            original_close(self)
            raise OSError(secret)

        monkeypatch.setattr(_Cache, "close", fail_cache_close)
    else:

        def fail(path):
            if (
                fault in ("receipt_read", "vendor_prefix")
                and Path(path).name.startswith("remote-artifacts-")
            ) or (fault == "artifact_read" and str(path).endswith(".png")):
                raise RuntimeError(secret) if fault == "vendor_prefix" else OSError(secret)

        case.sftp.before_read = fail
    with pytest.raises(ArtifactFailure) as caught:
        case.service.sync(snapshot, case.cache, threading.Event())
    detail = caught.value.failure
    assert detail.model_dump() == {"stage": stage, "code": code}
    assert "PASSWORD_SENTINEL" not in str(caught.value) + detail.model_dump_json()
    if fault in ("channel_cleanup", "cache_cleanup"):
        assert caught.value.cleanup_failure.stage == fault
    assert (case.cache / "artifact-index.json").exists() is (fault == "cache_cleanup")


def test_receipt_event_prefix_failure_has_owned_fixed_stage(case):
    running_receipt(case)
    with pytest.raises(ArtifactFailure) as caught:
        ArtifactSnapshot.verified(
            case.checkpoint, case.events, case.bundle_manifest, case.source_map, "0" * 64
        )
    assert caught.value.failure.model_dump() == {
        "stage": "event_prefix",
        "code": "SYNC_INVALID_EVIDENCE",
    }


def test_sync_diagnostic_event_is_application_only_and_strictly_fixed(case):
    value = dict(
        run_id=case.identity.run_id,
        seq=1,
        source="application",
        timestamp="fixture",
        type="artifact_sync_failed",
        payload={
            "failure": {"stage": "receipt_read", "code": "SYNC_IO_FAILED"},
            "cleanupFailure": None,
        },
    )
    assert Event.model_validate(value).payload == value["payload"]
    for invalid in (
        dict(value, source="runtime", source_seq=1),
        dict(value, block_id="arbitrary"),
        dict(value, payload={**value["payload"], "path": "/private"}),
        dict(
            value,
            payload={
                "failure": {"stage": "SDK_SECRET", "code": "SYNC_IO_FAILED"},
                "cleanupFailure": None,
            },
        ),
    ):
        with pytest.raises(ValueError):
            Event.model_validate(invalid)
