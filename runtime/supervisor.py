"""Portable POSIX owner. Fixed commands only; no SSH/application dependencies or PID kill API."""

import argparse
from contextlib import contextmanager
import fcntl
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import stat
import subprocess
import sys
import time
from uuid import UUID, uuid4

MAX_FILE = 8 * 1024 * 1024
MAX_STREAM = 128 * 1024 * 1024
FILES = {
    "code/train.py",
    "code/source-map.json",
    "code/entry.py",
    "code/easyai_runtime.py",
    "code/supervisor.py",
    "code/managed.py",
    "code/portable_journal.py",
    "program.ir.json",
    "README.md",
    "ENVIRONMENT.md",
}
IDENTITY_FIELDS = {
    "projectId",
    "targetId",
    "runId",
    "launchId",
    "username",
    "endpoint",
    "hostFingerprint",
    "runRoot",
    "programHash",
    "codeHash",
    "bundleHash",
    "configHash",
}
STREAMS = {
    "events": "logs/runtime-events.jsonl",
    "stdout": "logs/train.log",
    "stderr": "logs/stderr.log",
}


def unique(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("REMOTE_DUPLICATE_KEY")
        result[key] = value
    return result


def encoded(value):
    return json.dumps(
        value,
        sort_keys=True,
        ensure_ascii=False,
        allow_nan=False,
        separators=(",", ":"),
    ).encode()


def decoded(raw):
    return json.loads(
        raw,
        object_pairs_hook=unique,
        parse_constant=lambda value: (_ for _ in ()).throw(ValueError("REMOTE_NONFINITE")),
    )


def safe_file(info):
    if not stat.S_ISREG(info.st_mode) or info.st_uid != os.geteuid() or info.st_mode & 0o022:
        raise ValueError("REMOTE_FILE_UNSAFE")


class Root:
    def __init__(self, path):
        self.path = Path(path)
        if (
            os.name != "posix"
            or not self.path.is_absolute()
            or any(part in (".", "..") for part in path.split("/"))
        ):
            raise ValueError("REMOTE_ROOT_INVALID")
        descriptor = os.open(self.path.anchor, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        anchor_uid = os.fstat(descriptor).st_uid
        try:
            for index, part in enumerate(self.path.parts[1:]):
                parent_info = os.fstat(descriptor)
                self._directory(parent_info, False, anchor_uid)
                child = os.open(
                    part,
                    os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW,
                    dir_fd=descriptor,
                )
                os.close(descriptor)
                descriptor = child
            self._directory(os.fstat(descriptor), True, anchor_uid)
        except BaseException:
            os.close(descriptor)
            raise
        self.fd = descriptor
        self.identity = (os.fstat(descriptor).st_dev, os.fstat(descriptor).st_ino)

    def _directory(self, info, final, anchor_uid=None):
        owners = {os.geteuid()} if final else {0, os.geteuid(), anchor_uid}
        if (
            not stat.S_ISDIR(info.st_mode)
            or info.st_uid not in owners
            or (info.st_mode & 0o022 and (final or not info.st_mode & stat.S_ISVTX))
        ):
            raise ValueError("REMOTE_DIRECTORY_UNSAFE")

    def verify(self):
        current = Root(str(self.path))
        try:
            if current.identity != self.identity:
                raise ValueError("REMOTE_ROOT_REPLACED")
        finally:
            current.close()

    @contextmanager
    def parent(self, name):
        path = PurePosixPath(name)
        if (
            not name
            or path.is_absolute()
            or "\\" in name
            or any(part in ("", ".", "..") for part in name.split("/"))
        ):
            raise ValueError("REMOTE_PATH_INVALID")
        descriptor = os.dup(self.fd)
        try:
            for part in path.parts[:-1]:
                child = os.open(
                    part,
                    os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW,
                    dir_fd=descriptor,
                )
                os.close(descriptor)
                descriptor = child
                self._directory(os.fstat(descriptor), True)
            yield descriptor, path.name
        finally:
            os.close(descriptor)

    def open(self, name):
        with self.parent(name) as (parent, leaf):
            descriptor = os.open(leaf, os.O_RDONLY | os.O_NONBLOCK | os.O_NOFOLLOW, dir_fd=parent)
        try:
            safe_file(os.fstat(descriptor))
        except BaseException:
            os.close(descriptor)
            raise
        return os.fdopen(descriptor, "rb")

    def read(self, name, maximum=65536):
        with self.open(name) as source:
            if os.fstat(source.fileno()).st_size > maximum:
                raise ValueError("REMOTE_FILE_LIMIT")
            raw = source.read(maximum + 1)
            if len(raw) > maximum:
                raise ValueError("REMOTE_FILE_LIMIT")
            return raw

    def json(self, name):
        return decoded(self.read(name))

    def exists(self, name):
        try:
            with self.open(name):
                return True
        except FileNotFoundError:
            return False

    def directory(self, name):
        try:
            os.mkdir(name, 0o700, dir_fd=self.fd)
        except FileExistsError:
            pass
        descriptor = os.open(name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=self.fd)
        try:
            self._directory(os.fstat(descriptor), True)
        finally:
            os.close(descriptor)

    def write(self, name, value, *, once=False):
        self.verify()
        raw = encoded(value)
        if len(raw) > 65536:
            raise ValueError("REMOTE_RECORD_LIMIT")
        with self.parent(name) as (parent, leaf):
            try:
                info = os.stat(leaf, dir_fd=parent, follow_symlinks=False)
                safe_file(info)
            except FileNotFoundError:
                pass
            temporary = ".record-" + str(uuid4())
            descriptor = os.open(
                temporary,
                os.O_CREAT | os.O_EXCL | os.O_WRONLY | os.O_NOFOLLOW,
                0o600,
                dir_fd=parent,
            )
            try:
                with os.fdopen(descriptor, "wb") as output:
                    output.write(raw)
                    output.flush()
                    os.fsync(output.fileno())
                if once:
                    os.link(
                        temporary,
                        leaf,
                        src_dir_fd=parent,
                        dst_dir_fd=parent,
                        follow_symlinks=False,
                    )
                else:
                    os.replace(temporary, leaf, src_dir_fd=parent, dst_dir_fd=parent)
                os.fsync(parent)
            finally:
                try:
                    os.unlink(temporary, dir_fd=parent)
                except FileNotFoundError:
                    pass

    def lock(self, name):
        descriptor = os.open(
            name,
            os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW | os.O_NONBLOCK,
            0o600,
            dir_fd=self.fd,
        )
        try:
            safe_file(os.fstat(descriptor))
            fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BaseException:
            os.close(descriptor)
            raise
        return descriptor

    def close(self):
        os.close(self.fd)


def validate(root):
    identity, config, bundle = (
        root.json("remote-identity.json"),
        root.json("run-config.json"),
        root.json("bundle.json"),
    )
    if type(identity) is not dict or set(identity) != IDENTITY_FIELDS:
        raise ValueError("REMOTE_IDENTITY_INVALID")
    for key in ("projectId", "targetId", "runId", "launchId"):
        if str(UUID(identity[key])) != identity[key]:
            raise ValueError("REMOTE_IDENTITY_INVALID")
    for key in ("programHash", "codeHash", "bundleHash", "configHash"):
        if type(identity[key]) is not str or not re.fullmatch("[0-9a-f]{64}", identity[key]):
            raise ValueError("REMOTE_HASH_INVALID")
    if (
        type(identity["username"]) is not str
        or not 1 <= len(identity["username"]) <= 128
        or any(ord(char) < 33 or ord(char) == 127 for char in identity["username"])
    ):
        raise ValueError("REMOTE_IDENTITY_INVALID")
    if (
        type(identity["endpoint"]) is not dict
        or set(identity["endpoint"]) != {"host", "port"}
        or type(identity["endpoint"]["host"]) is not str
        or not identity["endpoint"]["host"]
        or type(identity["endpoint"]["port"]) is not int
        or not 1 <= identity["endpoint"]["port"] <= 65535
        or not re.fullmatch(r"SHA256:[A-Za-z0-9+/]{43}", identity["hostFingerprint"])
    ):
        raise ValueError("REMOTE_IDENTITY_INVALID")
    expected_config = {
        "configVersion",
        "runId",
        "projectId",
        "projectRevision",
        "programHash",
        "codeHash",
        "bundleHash",
        "targetId",
        "runner",
        "dataRoot",
        "runRoot",
        "pythonExecutable",
        "environmentPrefix",
        "condaExecutable",
        "device",
        "executionMode",
        "seed",
        "numWorkers",
        "pinMemoryPolicy",
        "quickLimits",
    }
    if (
        type(config) is not dict
        or set(config) != expected_config
        or config["configVersion"] != 1
        or config["runner"] != "ssh"
        or config["runRoot"] != str(root.path)
        or identity["runRoot"] != str(root.path)
        or config["pythonExecutable"] != sys.executable
        or config["device"] not in ("auto", "cpu", "cuda", "mps")
        or (
            config["environmentPrefix"] is not None
            and (
                sys.prefix != config["environmentPrefix"]
                or os.environ.get("CONDA_PREFIX") != config["environmentPrefix"]
                or not isinstance(config["condaExecutable"], str)
            )
        )
        or hashlib.sha256(
            json.dumps(config, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
        ).hexdigest()
        != identity["configHash"]
    ):
        raise ValueError("REMOTE_CONFIG_INVALID")
    if any(
        config[key] != identity[key]
        for key in (
            "runId",
            "projectId",
            "targetId",
            "programHash",
            "codeHash",
            "bundleHash",
        )
    ):
        raise ValueError("REMOTE_CONFIG_IDENTITY_INVALID")
    if (
        type(bundle) is not dict
        or set(bundle) != {"bundleHash", "programHash", "codeHash", "files"}
        or type(bundle["files"]) is not dict
        or set(bundle["files"]) != FILES
    ):
        raise ValueError("REMOTE_BUNDLE_INVALID")
    if hashlib.sha256(encoded(bundle["files"])).hexdigest() != identity["bundleHash"] or any(
        bundle[key] != identity[key] for key in ("bundleHash", "codeHash", "programHash")
    ):
        raise ValueError("REMOTE_BUNDLE_INVALID")
    with root.parent("code/train.py") as (code_dir, _):
        if set(os.listdir(code_dir)) != {
            PurePosixPath(name).name for name in FILES if name.startswith("code/")
        }:
            raise ValueError("REMOTE_UNHASHED_CODE_FORBIDDEN")
    total = 0
    for path, expected in bundle["files"].items():
        raw = root.read(path, MAX_FILE)
        total += len(raw)
        if total > 32 * 1024 * 1024 or hashlib.sha256(raw).hexdigest() != expected:
            raise ValueError("REMOTE_BUNDLE_INVALID")
    if bundle["files"]["code/train.py"] != identity["codeHash"]:
        raise ValueError("REMOTE_CODE_INVALID")
    return identity, config


def launch_record(root, identity):
    value = root.json("remote-launch.json")
    if (
        type(value) is not dict
        or set(value) != {"identity", "generations"}
        or value["identity"] != identity
        or set(value["generations"]) != set(STREAMS)
    ):
        raise ValueError("REMOTE_LAUNCH_INVALID")
    for generation in value["generations"].values():
        if str(UUID(generation)) != generation:
            raise ValueError("REMOTE_LAUNCH_INVALID")
    return value


def inspect(root, identity):
    if not root.exists("owner-status.json"):
        return None
    value = root.json("owner-status.json")
    if value.get("identity") != identity:
        raise ValueError("REMOTE_OWNER_MISMATCH")
    if not value.get("sealed"):
        beat = root.json("owner-heartbeat.json")
        age = time.monotonic() - beat["monotonic"]
        if (
            beat.get("launchId") != identity["launchId"]
            or beat.get("seq", 0) < value["heartbeat"]
            or not 0 <= age <= 3
        ):
            return None  # Stale owner is uncertain, never FAILED/CANCELLED or restartable.
    return value


def identity_digest(identity):
    # ASCII canonical JSON matches the authoritative application identity digest.
    return hashlib.sha256(
        json.dumps(identity, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    ).hexdigest()


def start(root, identity):
    lock = root.lock(".start.lock")
    try:
        if root.exists("remote-launch.json"):
            launch_record(root, identity)
            return identity  # All missing/stale owner cases remain inspect-only.
        root.write(
            "remote-launch.json",
            {
                "identity": identity,
                "generations": {name: str(uuid4()) for name in STREAMS},
            },
            once=True,
        )
        root.directory("logs")
        descriptors = []
        try:
            for name in ("owner.stdout", "owner.stderr"):
                descriptor = os.open(
                    "logs/" + name,
                    os.O_CREAT | os.O_EXCL | os.O_WRONLY | os.O_NOFOLLOW,
                    0o600,
                    dir_fd=root.fd,
                )
                descriptors.append(descriptor)
            subprocess.Popen(
                [
                    sys.executable,
                    "-I",
                    "-B",
                    str(root.path / "code/supervisor.py"),
                    "--serve",
                    "--run-dir",
                    str(root.path),
                    "--expected-identity",
                    identity_digest(identity),
                ],
                stdin=subprocess.DEVNULL,
                stdout=descriptors[0],
                stderr=descriptors[1],
                close_fds=True,
                start_new_session=True,
                cwd=root.path,
                env={
                    **os.environ,
                    "PYTHONDONTWRITEBYTECODE": "1",
                    "PYTHONNOUSERSITE": "1",
                    "PYTHONPATH": "",
                },
            )
        finally:
            for descriptor in descriptors:
                os.close(descriptor)
        return identity  # Receipt only, never a running/terminal claim.
    finally:
        os.close(lock)


def cancel(root, identity):
    launch_record(root, identity)
    value = inspect(root, identity)
    if value is not None and value["sealed"]:
        return identity
    request = {"identity": identity}
    if root.exists("remote-cancel.json"):
        if root.json("remote-cancel.json") != request:
            raise ValueError("REMOTE_CANCEL_IDENTITY_INVALID")
    else:
        root.write("remote-cancel.json", request, once=True)
    return identity  # The owner alone requests/signals its own managed child.


def stamp(root, name, generation):
    with root.open(name) as source:
        size = os.fstat(source.fileno()).st_size
        if size > MAX_STREAM:
            raise ValueError("REMOTE_STREAM_LIMIT")
        remaining, digest = size, hashlib.sha256()
        while remaining:
            raw = source.read(min(65536, remaining))
            if not raw:
                raise ValueError("REMOTE_STREAM_TRUNCATED")
            remaining -= len(raw)
            digest.update(raw)
    return {"generation": generation, "sizeBytes": size, "sha256": digest.hexdigest()}


def serve(root, identity, config):
    launch = launch_record(root, identity)
    lock = root.lock(".serve.lock")
    supervisor = None
    try:
        root.write("serve-claim.json", {"identity": identity}, once=True)
        for name in ("logs", "metrics", "cache"):
            root.directory(name)
        # -I deliberately excludes scriptdir. Only import sibling modules after full hash verification.
        sys.path.insert(0, str(root.path / "code"))
        from managed import ManagedProcess
        from portable_journal import PortableJournal

        environment = {
            "MPLBACKEND": "Agg",
            "OMP_NUM_THREADS": "1",
            "MKL_NUM_THREADS": "1",
            "MPLCONFIGDIR": str(root.path / "cache/matplotlib"),
            "XDG_CACHE_HOME": str(root.path / "cache"),
            "TORCH_HOME": str(root.path / "cache/torch"),
            "CUDA_CACHE_PATH": str(root.path / "cache/cuda"),
            "PYTORCH_KERNEL_CACHE_PATH": str(root.path / "cache/kernels"),
            "PYTHONUNBUFFERED": "1",
            "PYTHONDONTWRITEBYTECODE": "1",
            "PYTHONNOUSERSITE": "1",
            "PYTHONPATH": "",
        }
        supervisor = ManagedProcess(
            root.path,
            identity["runId"],
            [
                sys.executable,
                "-B",
                str(root.path / "code/entry.py"),
                "--config",
                str(root.path / "run-config.json"),
            ],
            root.path / "code",
            environment,
            journal_factory=PortableJournal,
        )
        spawn_failed = False
        try:
            supervisor.start()
        except Exception:
            events = supervisor.events()
            spawn_failed = len(events) == 1 and events[0].type == "process_spawn_failed"
            if not spawn_failed and supervisor.status != "FAILED":
                raise
        heartbeat = 0
        receipt, receipt_records = None, []
        receipt_count = 0
        while True:
            supervisor._done.wait(0.1)
            try:
                cancellation = root.json("remote-cancel.json")
            except (OSError, ValueError):
                cancellation = None
            if cancellation == {"identity": identity}:
                supervisor.request_cancel()
            with supervisor.snapshot() as (state, done, exit_code):
                heartbeat += 1
                sealed = done and state in ("COMPLETED", "FAILED", "CANCELLED")
                streams = {
                    name: stamp(root, path, launch["generations"][name])
                    for name, path in STREAMS.items()
                }
                manifest = artifact_manifest(identity, supervisor.events(), streams)
                records = manifest["artifacts"]
                if records != receipt_records or sealed:
                    # Each immutable event may introduce one artifact; at most
                    # 256 growing snapshots plus the final sealed receipt.
                    if records[: len(receipt_records)] != receipt_records or receipt_count >= 257:
                        raise ValueError("REMOTE_ARTIFACT_RECEIPT_CHANGED")
                    raw = encoded(manifest)
                    digest = hashlib.sha256(raw).hexdigest()
                    name = "remote-artifacts-" + digest + ".json"
                    try:
                        root.write(name, manifest, once=True)
                    except FileExistsError:
                        if root.read(name) != raw:
                            raise ValueError("REMOTE_ARTIFACT_RECEIPT_CHANGED")
                    receipt = {
                        "sha256": digest,
                        "sourceSeq": manifest["sourceSeq"],
                        "eventsSha256": manifest["eventsSha256"],
                    }
                    receipt_records = list(records)
                    receipt_count += 1
                status = {
                    "identity": identity,
                    "heartbeat": heartbeat,
                    "artifactReceipt": receipt,
                    "state": state,
                    "sealed": sealed,
                    "spawnFailed": spawn_failed,
                    "exitCode": exit_code if sealed else None,
                    "streams": streams,
                }
            root.write(
                "owner-heartbeat.json",
                {
                    "launchId": identity["launchId"],
                    "seq": heartbeat,
                    "monotonic": time.monotonic(),
                },
            )
            # The receipt must be durable before publishing a sealed observation.
            # Failure leaves an unsealed/stale owner, never a fictitious ready result.
            if sealed:
                root.write(
                    "remote-artifacts.json",
                    artifact_manifest(identity, supervisor.events(), streams),
                )
            root.write("owner-status.json", status)
            if sealed:
                return
    finally:
        if supervisor is not None:
            supervisor.close()
        os.close(lock)


def artifact_manifest(identity, events, streams):
    """Receipt only: downstream verifies records against its committed event journal."""
    records = [event.payload for event in events if event.type == "artifact_created"]
    if len(records) > 256:
        raise ValueError("REMOTE_ARTIFACT_LIMIT")
    total = 0
    for record in records:
        size = record.get("sizeBytes")
        if type(size) is not int or not 0 <= size <= 100 * 1024 * 1024:
            raise ValueError("REMOTE_ARTIFACT_LIMIT")
        total += size
    if total > 256 * 1024 * 1024:
        raise ValueError("REMOTE_ARTIFACT_LIMIT")
    return {
        "protocolVersion": 1,
        "identity": identity,
        "uid": os.geteuid(),
        "sourceSeq": events[-1].value["sourceSeq"] if events else 0,
        "eventsSha256": streams["events"]["sha256"],
        "artifacts": records,
    }


def main():
    parser = argparse.ArgumentParser(description="Fixed detached owner protocol")
    action = parser.add_mutually_exclusive_group(required=True)
    for name in ("start", "serve", "inspect", "cancel"):
        action.add_argument("--" + name, action="store_true")
    parser.add_argument("--run-dir", required=True)
    parser.add_argument("--expected-identity", required=True)
    args = parser.parse_args()
    root = Root(args.run_dir)
    try:
        identity, config = validate(root)
        if (
            not re.fullmatch("[0-9a-f]{64}", args.expected_identity)
            or identity_digest(identity) != args.expected_identity
        ):
            raise ValueError("REMOTE_EXPECTED_IDENTITY_MISMATCH")
        if args.start:
            result = start(root, identity)
        elif args.serve:
            serve(root, identity, config)
            return
        elif args.inspect:
            launch_record(root, identity)
            result = inspect(root, identity)
        else:
            result = cancel(root, identity)
        print(encoded(result).decode(), flush=True)
    finally:
        root.close()


if __name__ == "__main__":
    try:
        main()
    except Exception:
        # Do not print SDK/OS/argv/config/raw exception text into a shared terminal.
        print('{"error":"REMOTE_OWNER_PROTOCOL_FAILED"}', file=sys.stderr, flush=True)
        sys.exit(1)
