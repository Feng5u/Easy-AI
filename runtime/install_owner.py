"""Fixed Linux install-owner RPC. Standard library only; never resolves/downloads packages.

The authenticated application supplies source configuration and fixed command argv.
No action deletes environment/user paths; publication removes only its own temporary file.
An uncertain phase is a permanent barrier until its owner
has written a quiet terminal receipt; a missing ACK never permits another launch.
"""

import argparse
from contextlib import contextmanager
from datetime import datetime, timezone
from email.parser import BytesParser
import fcntl
import hashlib
import importlib.util
from itertools import islice
import json
import os
from pathlib import Path
import platform
import re
import stat
import subprocess
import sys
import time
from uuid import UUID, uuid4

MAX_JSON = 4 * 1024 * 1024
MAX_SOURCE = 1024 * 1024 * 1024
QUIET = {"completed", "cancelled", "failed"}
IDENTITY = {
    "projectId",
    "targetId",
    "targetRevision",
    "endpoint",
    "hostFingerprint",
    "username",
}


def fail(code):
    raise ValueError(code)


def encoded(value):
    return json.dumps(
        value,
        sort_keys=True,
        ensure_ascii=False,
        allow_nan=False,
        separators=(",", ":"),
    ).encode()


def digest(value):
    return hashlib.sha256(encoded(value)).hexdigest()


def unique(pairs):
    value = {}
    for key, item in pairs:
        if key in value:
            fail("INSTALL_DUPLICATE_KEY")
        value[key] = item
    return value


def decoded(raw):
    return json.loads(
        raw,
        object_pairs_hook=unique,
        parse_constant=lambda _: fail("INSTALL_JSON_INVALID"),
    )


def identifier(value):
    if not isinstance(value, str) or str(UUID(value)) != value:
        fail("INSTALL_ID_INVALID")
    return value


def sha(value):
    if not isinstance(value, str) or not re.fullmatch("[a-f0-9]{64}", value):
        fail("INSTALL_HASH_INVALID")
    return value


def absolute(value):
    if (
        not isinstance(value, str)
        or not value.startswith("/")
        or "\\" in value
        or any(p in ("", ".", "..") for p in value.split("/")[1:])
    ):
        fail("INSTALL_PATH_INVALID")
    return Path(value)


def directory_fd(path, *, owned=False):
    """Walk with O_NOFOLLOW; /tmp-style sticky ancestors are permitted, never the root."""
    path = absolute(str(path))
    fd = os.open("/", os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    anchor_uid = os.fstat(fd).st_uid
    try:
        for index, part in enumerate(path.parts[1:]):
            child = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
            os.close(fd)
            fd = child
            info = os.fstat(fd)
            final = index == len(path.parts) - 2
            if info.st_uid not in (
                {os.getuid()} if final and owned else {0, os.getuid(), anchor_uid}
            ) or (info.st_mode & 0o022 and (final or not info.st_mode & stat.S_ISVTX)):
                fail("INSTALL_DIRECTORY_UNSAFE")
        return fd
    except BaseException:
        os.close(fd)
        raise


def directory(path, *, owned=False):
    fd = directory_fd(path, owned=owned)
    try:
        return os.fstat(fd)
    finally:
        os.close(fd)


def open_file(path, flags, mode=0o600, *, owned=False):
    parent = directory_fd(path.parent, owned=owned)
    try:
        return os.open(path.name, flags, mode, dir_fd=parent)
    finally:
        os.close(parent)


def file_read(path, limit=MAX_JSON):
    fd = open_file(path, os.O_RDONLY | os.O_NONBLOCK | os.O_NOFOLLOW)
    with os.fdopen(fd, "rb") as stream:
        before = os.fstat(stream.fileno())
        if (
            not stat.S_ISREG(before.st_mode)
            or before.st_uid not in {0, os.getuid()}
            or before.st_mode & 0o022
            or before.st_nlink != 1
            or before.st_size > limit
        ):
            fail("INSTALL_FILE_UNSAFE")
        content = stream.read(limit + 1)
        after = os.fstat(stream.fileno())

        def stamp(info):
            return (
                info.st_dev,
                info.st_ino,
                info.st_size,
                info.st_mtime_ns,
                info.st_ctime_ns,
            )

        current = path.lstat()
        if (
            stamp(before) != stamp(after)
            or len(content) != before.st_size
            or (current.st_dev, current.st_ino) != (before.st_dev, before.st_ino)
        ):
            fail("INSTALL_SOURCE_CHANGED")
        return content, stamp(before)


def read_json(path):
    return decoded(file_read(path)[0])


def fsync_dir(path):
    fd = directory_fd(path, owned=True)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def write_file(path, content):
    fd = open_file(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, owned=True)
    with os.fdopen(fd, "wb") as output:
        output.write(content)
        output.flush()
        os.fsync(output.fileno())
    fsync_dir(path.parent)


def write_json(path, value):
    write_file(path, encoded(value))


def publish_status(path, value):
    """Publish a complete durable receipt once, never replacing any existing inode."""
    import ctypes

    temporary = path.with_name("easyai-status-" + str(uuid4()))
    write_json(temporary, value)
    parent = directory_fd(path.parent, owned=True)
    try:
        # Linux renameat2(RENAME_NOREPLACE) exposes only the complete, single-link
        # inode. link/unlink would expose nlink/ctime transitions to file_read.
        rename = getattr(ctypes.CDLL(None, use_errno=True), "renameat2", None)
        if rename is None:
            fail("INSTALL_ATOMIC_PUBLISH_UNAVAILABLE")
        rename.argtypes = [
            ctypes.c_int,
            ctypes.c_char_p,
            ctypes.c_int,
            ctypes.c_char_p,
            ctypes.c_uint,
        ]
        rename.restype = ctypes.c_int
        if rename(parent, os.fsencode(temporary.name), parent, os.fsencode(path.name), 1) != 0:
            error = ctypes.get_errno()
            raise OSError(error, os.strerror(error), str(path))
        os.fsync(parent)
    finally:
        # Only our private temporary name may be removed; final status is immutable,
        # including malformed/unknown pre-existing evidence. Never retry publication.
        try:
            os.unlink(temporary.name, dir_fd=parent)
        except FileNotFoundError:
            pass
        os.close(parent)


def replace_json(path, value):
    if path.exists():
        file_read(path)
    temporary = path.with_name("easyai-atomic-" + str(uuid4()))
    write_json(temporary, value)
    parent = directory_fd(path.parent, owned=True)
    try:
        os.replace(temporary.name, path.name, src_dir_fd=parent, dst_dir_fd=parent)
    finally:
        os.close(parent)
    fsync_dir(path.parent)


def mkdir(path):
    parent = directory_fd(path.parent, owned=True)
    try:
        try:
            os.mkdir(path.name, mode=0o700, dir_fd=parent)
            os.fsync(parent)
        except FileExistsError:
            pass
    finally:
        os.close(parent)
    directory(path, owned=True)


def new_directory(path):
    parent = directory_fd(path.parent, owned=True)
    try:
        os.mkdir(path.name, mode=0o700, dir_fd=parent)
        os.fsync(parent)
    finally:
        os.close(parent)
    directory(path, owned=True)


@contextmanager
def lock(path, pending=None):
    fd = open_file(path, os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW | os.O_NONBLOCK, owned=True)
    try:
        info = os.fstat(fd)
        if (
            not stat.S_ISREG(info.st_mode)
            or info.st_uid != os.getuid()
            or info.st_mode & 0o077
            or info.st_nlink != 1
        ):
            fail("INSTALL_LOCK_UNSAFE")
        deadline = time.monotonic() + 2
        while True:
            try:
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except BlockingIOError:
                if pending is None or time.monotonic() >= deadline:
                    fail("INSTALL_WRITER_BUSY")
                pending()  # Revalidate the same durable phase/intent on every wait.
                time.sleep(0.01)
        if pending is not None:
            pending()  # Also close the final wait→acquire intent-change window.
        yield fd
    finally:
        os.close(fd)


@contextmanager
def inherited_lock(path, fd):
    if fd is None:
        with lock(path) as owned:
            yield owned
        return
    if type(fd) is not int or fd < 0:
        fail("INSTALL_LOCK_UNSAFE")
    try:
        info = os.fstat(fd)
        expected = os.stat(path, follow_symlinks=False)
        if (
            not stat.S_ISREG(info.st_mode)
            or info.st_uid != os.getuid()
            or info.st_mode & 0o077
            or info.st_nlink != 1
            or (info.st_dev, info.st_ino) != (expected.st_dev, expected.st_ino)
        ):
            fail("INSTALL_LOCK_UNSAFE")
        # Same open-file description: the parent's flock remains continuously held.
        # Do not LOCK_UN: the parent can still own its copy of this descriptor.
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        yield fd
    finally:
        os.close(fd)


def archive(item):
    if not isinstance(item, dict) or set(item) != {"path", "sha256", "bytes"}:
        fail("INSTALL_ARCHIVE_INVALID")
    path = absolute(item["path"])
    sha(item["sha256"])
    if type(item["bytes"]) is not int or not 1 <= item["bytes"] <= MAX_SOURCE:
        fail("INSTALL_ARCHIVE_INVALID")
    checksum, stamp = file_hash(path)
    if stamp[2] != item["bytes"] or checksum != item["sha256"]:
        fail("INSTALL_SOURCE_CHANGED")
    return {"path": str(path), "stamp": stamp, "sha256": item["sha256"]}


def file_hash(path):
    fd = open_file(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(fd, "rb") as stream:
        before = os.fstat(stream.fileno())
        if (
            not stat.S_ISREG(before.st_mode)
            or before.st_uid not in {0, os.getuid()}
            or before.st_mode & 0o022
            or before.st_nlink != 1
            or before.st_size > MAX_SOURCE
        ):
            fail("INSTALL_FILE_UNSAFE")
        checksum, total = hashlib.sha256(), 0
        while chunk := stream.read(1024 * 1024):
            total += len(chunk)
            if total > MAX_SOURCE:
                fail("INSTALL_SOURCE_LIMIT")
            checksum.update(chunk)
        after = os.fstat(stream.fileno())

        def stamp(info):
            return (
                info.st_dev,
                info.st_ino,
                info.st_size,
                info.st_mtime_ns,
                info.st_ctime_ns,
            )

        current = path.lstat()
        if (
            stamp(before) != stamp(after)
            or total != before.st_size
            or (current.st_dev, current.st_ino) != (before.st_dev, before.st_ino)
        ):
            fail("INSTALL_SOURCE_CHANGED")
        return checksum.hexdigest(), stamp(before)


def tree(root):
    directory(root)
    records, total, count = [], 0, 0
    for current, names, files in os.walk(root, followlinks=False):
        names.sort()
        files.sort()
        count += len(names) + len(files)
        if count > 10000:
            fail("INSTALL_SOURCE_LIMIT")
        for name in names:
            directory(Path(current) / name)
        for name in files:
            path = Path(current) / name
            checksum, stamp = file_hash(path)
            total += stamp[2]
            if total > MAX_SOURCE:
                fail("INSTALL_SOURCE_LIMIT")
            records.append((str(path.relative_to(root)), checksum))
    return digest(sorted(records)), total


class Context:
    def __init__(self, request):
        if sys.platform != "linux" or platform.machine().lower() not in {
            "x86_64",
            "amd64",
        }:
            fail("INSTALL_PLATFORM_UNSUPPORTED")
        if sys.version_info[:2] != (3, 11):
            fail("INSTALL_HELPER_PYTHON_UNSUPPORTED")
        self.request = request
        self.config = request["configuration"]
        config_keys = {
            "root",
            "launcher",
            "module_root",
            "module_tree_sha256",
            "bootstrap",
            "wheelhouse",
            "disk_budget_bytes",
            "seconds",
            "execution_authorized",
            "authorization_expires",
        }
        if (
            not isinstance(self.config, dict)
            or not config_keys <= set(self.config)
            or not set(self.config) <= config_keys | {"schema_version", "conda_version"}
        ):
            fail("INSTALL_CONFIGURATION_INVALID")
        self.identity = request["identity"]
        if (
            not isinstance(self.identity, dict)
            or set(self.identity) != IDENTITY
            or not isinstance(self.identity["endpoint"], dict)
            or set(self.identity["endpoint"]) != {"host", "port"}
            or type(self.identity["targetRevision"]) is not int
            or self.identity["targetRevision"] < 1
        ):
            fail("INSTALL_IDENTITY_INVALID")
        for key in ("projectId", "targetId"):
            identifier(self.identity[key])
        if (
            any(
                not isinstance(self.identity[k], str)
                or not self.identity[k]
                or len(self.identity[k]) > 512
                for k in ("hostFingerprint", "username")
            )
            or not isinstance(self.identity["endpoint"]["host"], str)
            or type(self.identity["endpoint"]["port"]) is not int
            or not 1 <= self.identity["endpoint"]["port"] <= 65535
        ):
            fail("INSTALL_IDENTITY_INVALID")
        self.env = identifier(request["environmentId"])
        if type(request["newEnvironment"]) is not bool:
            fail("INSTALL_CONFIGURATION_INVALID")
        self.new = request["newEnvironment"]
        self.root = absolute(self.config["root"])
        info = directory(self.root, owned=True)
        self.root_inode = [info.st_dev, info.st_ino]
        marker = read_json(self.root / ".easyai-install-root.json")
        if encoded(marker) != encoded(
            {"ownedByEasyAI": True, "uid": os.getuid(), "protocolVersion": 1}
        ):
            fail("INSTALL_ROOT_NOT_OWNED")
        self.prefix = self.root / "training-environments" / self.env
        self.slot = self.root / "environment-creations" / self.env
        if (
            type(self.config["disk_budget_bytes"]) is not int
            or not 1 <= self.config["disk_budget_bytes"] <= 10 * MAX_SOURCE
            or type(self.config["seconds"]) is not int
            or not 1 <= self.config["seconds"] <= 3600
        ):
            fail("INSTALL_BUDGET_INVALID")
        self.budget = self.config["disk_budget_bytes"]
        self.authority_fingerprint = digest(
            {
                "root": self.root_inode,
                "identity": self.identity,
                "configuration": {
                    k: v
                    for k, v in self.config.items()
                    if k not in {"execution_authorized", "authorization_expires"}
                },
            }
        )
        self.recovery = request.get("action") in {"inspect", "cancel", "release"}
        if self.recovery:
            # Recovery cannot be disabled by deleted sources or expired execution permission.
            # The durable claim still binds immutable root/identity/configuration authority.
            self.source_fingerprint = None
            return
        launcher = archive(self.config["launcher"])
        modules = absolute(self.config["module_root"])
        module_hash, module_bytes = tree(modules)
        if module_hash != self.config["module_tree_sha256"]:
            fail("INSTALL_SOURCE_CHANGED")
        bootstrap = self.config["bootstrap"]
        if not isinstance(bootstrap, list) or not 1 <= len(bootstrap) <= 128:
            fail("INSTALL_ARCHIVE_INVALID")
        boot = [archive(item) for item in bootstrap]
        self.bootstrap_bytes = sum(item["bytes"] for item in bootstrap)
        wheelhouse = absolute(self.config["wheelhouse"])
        directory(wheelhouse)
        wheels = request["wheels"]
        if not isinstance(wheels, list) or len(wheels) > 256:
            fail("INSTALL_ARCHIVE_INVALID")
        stamps, filenames = [], set()
        for item in wheels:
            if (
                not isinstance(item, dict)
                or set(item) != {"name", "version", "filename", "sha256", "downloadBytes"}
                or not isinstance(item["filename"], str)
                or not re.fullmatch(r"[A-Za-z0-9_.+-]+\.whl", item["filename"])
                or item["filename"] in filenames
            ):
                fail("INSTALL_WHEEL_INVALID")
            filenames.add(item["filename"])
            stamps.append(
                archive(
                    {
                        "path": str(wheelhouse / item["filename"]),
                        "sha256": item["sha256"],
                        "bytes": item["downloadBytes"],
                    }
                )
            )
        self.source_bytes = (
            self.config["launcher"]["bytes"]
            + module_bytes
            + self.bootstrap_bytes
            + sum(w["downloadBytes"] for w in wheels)
        )
        resource_checks = request.get("action") not in {"inspect", "cancel", "release"}
        if resource_checks and self.source_bytes > self.budget:
            fail("INSTALL_DISK_BUDGET_EXCEEDED")
        free = os.statvfs(self.root)
        self.free_bytes = free.f_bavail * free.f_frsize
        if resource_checks and self.free_bytes < self.budget:
            fail("INSTALL_FREE_SPACE_INSUFFICIENT")
        self.source_fingerprint = digest(
            {
                "root": self.root_inode,
                "identity": self.identity,
                "configuration": self.config,
                "wheels": wheels,
                "launcher": launcher,
                "moduleHash": module_hash,
                "moduleIdentity": [modules.stat().st_dev, modules.stat().st_ino],
                "bootstrap": boot,
                "wheelStamps": stamps,
            }
        )

    def authorized(self):
        expires = datetime.fromisoformat(
            self.config["authorization_expires"].replace("Z", "+00:00")
        )
        if (
            self.config.get("execution_authorized") is not True
            or expires.tzinfo is None
            or expires <= datetime.now(timezone.utc)
        ):
            fail("INSTALL_EXECUTION_NOT_AUTHORIZED")

    def prefix_info(self, *, allow_empty=False):
        directory(self.prefix.parent, owned=True) if self.prefix.parent.exists() else None
        try:
            info = directory(self.prefix, owned=True)
        except FileNotFoundError:
            return None, False
        marker = self.prefix / ".easyai-owned.json"
        if not marker.exists():
            if not allow_empty:
                fail("INSTALL_ENVIRONMENT_NOT_OWNED")
            return [info.st_dev, info.st_ino], False
        if encoded(read_json(marker)) != encoded(
            {"ownedByEasyAI": True, "environmentId": self.env}
        ):
            fail("INSTALL_ENVIRONMENT_NOT_OWNED")
        return [info.st_dev, info.st_ino], True

    def job(self):
        job = identifier(self.request["jobId"])
        plan = sha(self.request["planHash"])
        path = self.slot / "jobs" / job
        claim = read_json(path / "claim.json")
        expected = {
            "environmentId": self.env,
            "jobId": job,
            "planHash": plan,
            "identity": self.identity,
            "sourceFingerprint": claim.get("sourceFingerprint")
            if self.recovery
            else self.source_fingerprint,
            "authorityFingerprint": self.authority_fingerprint,
            "newEnvironment": claim.get("newEnvironment") if self.recovery else self.new,
        }
        if claim != expected:
            fail("INSTALL_CLAIM_MISMATCH")
        return path, claim

    def allocation(self):
        value = read_json(self.slot / "allocation.json")
        inode, _ = self.prefix_info(allow_empty=True)
        if (
            value
            != {
                "environmentId": self.env,
                "prefixIdentity": inode,
                "identity": self.identity,
            }
            or inode is None
        ):
            fail("INSTALL_PREFIX_REPLACED")
        return inode


def inventory(context):
    inode, owned = context.prefix_info()
    if not inode:
        return inode, owned, {}, []
    base = context.prefix / "lib" / "python3.11" / "site-packages"
    versions, records = {}, []
    if base.exists():
        directory(base, owned=True)
        with os.scandir(base) as scanner:
            entries = [base / entry.name for entry in islice(scanner, 10001)]
        if len(entries) > 10000:
            fail("INSTALL_INVENTORY_LIMIT")
        for entry in sorted(entries):
            if not entry.name.endswith(".dist-info"):
                continue
            directory(entry, owned=True)
            raw, _ = file_read(entry / "METADATA", 2 * 1024 * 1024)
            metadata = BytesParser().parsebytes(raw, headersonly=True)
            name, version = metadata.get("Name"), metadata.get("Version")
            if (
                not name
                or not version
                or not re.fullmatch(r"[A-Za-z0-9_.-]{1,128}", name)
                or len(version) > 128
            ):
                fail("INSTALL_METADATA_INVALID")
            name = re.sub(r"[-_.]+", "-", name).lower()
            if name in versions:
                fail("INSTALL_METADATA_AMBIGUOUS")
            versions[name] = version
            records.append((entry.name, hashlib.sha256(raw).hexdigest()))
    return inode, owned, versions, records


def snapshot(context):
    inode, owned, versions, records = inventory(context)
    ready = False
    if owned and (context.slot / "ready.json").exists():
        receipt = read_json(context.slot / "ready.json")
        if (
            receipt.get("prefixIdentity") == inode
            and receipt.get("identity") == context.identity
            and (context.slot / "jobs" / identifier(receipt["jobId"]) / "closed.json").exists()
        ):
            closed = read_json(context.slot / "jobs" / receipt["jobId"] / "closed.json")
            ready = closed == {
                "jobId": receipt["jobId"],
                "planHash": receipt["planHash"],
                "identity": context.identity,
                "prefixIdentity": inode,
            }
            if ready:
                ready = (
                    read_json(context.slot / "jobs" / receipt["jobId"] / "ready.json") == receipt
                )
    if ready and (context.slot / "last-writer.json").exists():
        ready = read_json(context.slot / "last-writer.json") == {
            "jobId": receipt["jobId"],
            "planHash": receipt["planHash"],
            "identity": context.identity,
        }
    if inode and not context.new and not ready:
        fail("INSTALL_ENVIRONMENT_NOT_READY")
    return {
        "root": str(context.root),
        "prefix": str(context.prefix),
        "uid": os.getuid(),
        "platform": "linux-x86_64-cp311",
        "pythonVersion": platform.python_version(),
        "prefixIdentity": inode,
        "owned": owned,
        "ready": ready,
        "sourceFingerprint": context.source_fingerprint,
        "fingerprint": digest(
            {
                "source": context.source_fingerprint,
                "prefix": inode,
                "versions": versions,
                "inventory": records,
                "owned": owned,
                "ready": ready,
            }
        ),
        "versions": versions,
        "bootstrapBytes": context.bootstrap_bytes,
        "sourceBytes": context.source_bytes,
        "freeBytes": context.free_bytes,
    }


def claim_fields(context):
    return {
        "environmentId": context.env,
        "jobId": identifier(context.request["jobId"]),
        "planHash": sha(context.request["planHash"]),
        "identity": context.identity,
        "sourceFingerprint": context.source_fingerprint,
        "authorityFingerprint": context.authority_fingerprint,
        "newEnvironment": context.new,
    }


def reserve(context):
    context.authorized()
    mkdir(context.root / "environment-creations")
    mkdir(context.slot)
    with lock(context.slot / ".writer.lock"):
        claim = claim_fields(context)
        jobs = context.slot / "jobs"
        mkdir(jobs)
        target = jobs / claim["jobId"]
        if target.exists():
            context.job()
            if (target / "closed.json").exists():
                fail("INSTALL_CLAIM_CLOSED")
            return {"ack": True}
        for entry in jobs.iterdir():
            directory(entry, owned=True)
            prior = read_json(entry / "claim.json")
            if prior["identity"] != context.identity or not (entry / "closed.json").exists():
                fail("INSTALL_RESERVATION_BUSY")
            closed = read_json(entry / "closed.json")
            if (
                closed.get("jobId") != prior["jobId"]
                or closed.get("planHash") != prior["planHash"]
                or closed.get("identity") != context.identity
            ):
                fail("INSTALL_RESERVATION_BUSY")
        if (context.slot / "claim.json").exists():
            origin = read_json(context.slot / "claim.json")
            if origin["identity"] != context.identity or context.new:
                fail("INSTALL_RESERVATION_BUSY")
            snapshot(context)
        else:
            if context.new:
                if context.prefix.exists() or context.prefix.is_symlink():
                    fail("INSTALL_PREFIX_EXISTS")
            else:
                inode, owned = context.prefix_info()
                if not inode or not owned:
                    fail("INSTALL_ENVIRONMENT_NOT_OWNED")
                snapshot(context)  # Existing environment needs a closed ready receipt.
                write_json(
                    context.slot / "allocation.json",
                    {
                        "environmentId": context.env,
                        "prefixIdentity": inode,
                        "identity": context.identity,
                    },
                )
            write_json(context.slot / "claim.json", claim)
        new_directory(target)
        write_json(target / "claim.json", claim)
        mkdir(target / "phases")
        return {"ack": True}


def usage(prefix):
    total = count = 0
    for current, dirs, files in os.walk(prefix, followlinks=False):
        directory(Path(current), owned=True)
        count += len(dirs) + len(files)
        if count > 200000:
            fail("INSTALL_PREFIX_LIMIT")
        for name in dirs:
            directory(Path(current) / name, owned=True)
        for name in files:
            path = Path(current) / name
            info = path.lstat()
            if info.st_uid != os.getuid():
                fail("INSTALL_PREFIX_UNSAFE")
            if stat.S_ISLNK(info.st_mode):
                resolved = path.resolve(strict=True)
                if not resolved.is_relative_to(prefix) or not resolved.is_file():
                    fail("INSTALL_PREFIX_UNSAFE")
            elif not stat.S_ISREG(info.st_mode) or info.st_mode & 0o022:
                fail("INSTALL_PREFIX_UNSAFE")
            total += info.st_size
    return total


def occupied(context, job):
    total = usage(context.prefix) if context.prefix.exists() else 0
    workspace = context.root / "install-processes" / job.name
    if workspace.exists():
        total += usage(workspace)
    return total


def phase_path(context, job):
    return context.root / "install-processes" / job.name / identifier(context.request["phase"])


def selected_phase(context, job):
    if context.request.get("phase") is not None:
        return identifier(context.request["phase"])
    latest = job / "last-phase.json"
    if latest.exists():
        value = read_json(latest)
        if (
            set(value) != {"phase", "jobId", "planHash"}
            or value["jobId"] != job.name
            or value["planHash"] != context.request["planHash"]
        ):
            fail("INSTALL_PHASE_MISMATCH")
        return identifier(value["phase"])
    return None


def intent_check(context, path):
    intent = read_json(path / "intent.json")
    if (
        intent["jobId"] != context.request["jobId"]
        or intent["planHash"] != context.request["planHash"]
        or intent["identity"] != context.identity
        or intent["phase"] != context.request["phase"]
        or (not context.recovery and intent["sourceFingerprint"] != context.source_fingerprint)
    ):
        fail("INSTALL_PHASE_MISMATCH")
    return intent


def inspect_phase(context, job):
    phase = selected_phase(context, job)
    if phase is None:
        process_job = context.root / "install-processes" / job.name
        directory(job / "phases", owned=True)
        with os.scandir(job / "phases") as scanner:
            indexed = next(scanner, None) is not None
        unindexed = False
        if process_job.exists():
            directory(process_job, owned=True)
            with os.scandir(process_job) as scanner:
                unindexed = next(scanner, None) is not None
        untouched = not indexed and not unindexed
        return {
            "phase": None,
            "jobId": context.request["jobId"],
            "planHash": context.request["planHash"],
            "outcome": "not_dispatched" if untouched else "unknown",
            "dispatched": not untouched,
            "quiescent": untouched,
            "events": [],
        }
    context.request = dict(context.request, phase=phase)
    path = phase_path(context, job)
    result = {
        "phase": context.request["phase"],
        "jobId": context.request["jobId"],
        "planHash": context.request["planHash"],
        "outcome": "unknown",
        "quiescent": False,
        "events": [],
        "phaseRoot": str(path),
        "dispatched": True,
    }
    if not path.exists():
        return result
    intent_check(context, path)
    if (path / "status.json").exists():
        value = read_json(path / "status.json")
        if (
            value.get("phase") != result["phase"]
            or value.get("jobId") != result["jobId"]
            or value.get("planHash") != result["planHash"]
            or value.get("outcome") not in QUIET | {"unknown"}
            or type(value.get("quiescent")) is not bool
            or (value["quiescent"] and value["outcome"] not in QUIET)
        ):
            fail("INSTALL_PHASE_INVALID")
        return value
    return result


def settling_owner(context, job):
    receipt = inspect_phase(context, job)
    phase = receipt.get("phase")
    if phase is None or not receipt["quiescent"]:
        return None
    expected = {"phase": phase, "jobId": job.name, "planHash": context.request["planHash"]}

    def revalidate():
        context.job()
        if read_json(job / "last-phase.json") != expected:
            fail("INSTALL_PHASE_MISMATCH")
        intent_check(context, phase_path(context, job))

    revalidate()
    return revalidate


def run_phase(context, job, writer_fd):
    context.authorized()
    path = phase_path(context, job)
    index = job / "phases" / context.request["phase"]
    if path.exists() or index.exists():
        return inspect_phase(context, job)
    for other in (job / "phases").iterdir():
        previous = dict(context.request, phase=identifier(other.name))
        old_request = context.request
        try:
            context.request = previous
            if not inspect_phase(context, job)["quiescent"]:
                fail("INSTALL_PHASE_UNCONFIRMED")
        finally:
            context.request = old_request
    argv, environment, helpers = (context.request[k] for k in ("argv", "environment", "helpers"))
    files = context.request.get("files", {})
    if (
        not isinstance(argv, list)
        or not argv
        or len(argv) > 256
        or any(not isinstance(a, str) or "\x00" in a or len(a) > 16384 for a in argv)
        or not Path(argv[0]).is_absolute()
        or not isinstance(environment, dict)
        or len(environment) > 128
        or any(
            not isinstance(k, str)
            or not re.fullmatch("[A-Za-z_][A-Za-z0-9_]*", k)
            or not isinstance(v, str)
            or "\x00" in v
            or len(v) > 16384
            for k, v in environment.items()
        )
        or not isinstance(helpers, dict)
        or set(helpers) != {"managed.py", "portable_journal.py"}
        or not isinstance(files, dict)
        or not set(files) <= {"requirements.lock", "explicit.txt", "condarc"}
        or any(
            not isinstance(text, str) or len(text.encode()) > MAX_JSON for text in files.values()
        )
    ):
        fail("INSTALL_COMMAND_INVALID")
    helper_source = context.request["helperSource"]
    current_source = globals().get("__easyai_install_source__")
    if current_source is None:
        current_source = file_read(Path(__file__).absolute())[0].decode("utf-8")
    if (
        not isinstance(helper_source, str)
        or helper_source != current_source
        or any(
            not isinstance(text, str) or len(text.encode()) > MAX_JSON for text in helpers.values()
        )
    ):
        fail("INSTALL_HELPER_CHANGED")
    inode = context.allocation()
    if not context.new:
        context.prefix_info()  # Existing writers always require the owned marker.
    if occupied(context, job) > context.budget:
        fail("INSTALL_DISK_BUDGET_EXCEEDED")
    mkdir(context.root / "install-processes")
    mkdir(context.root / "install-processes" / job.name)
    # Index first: even a crash before directory/intent creation blocks every new phase.
    write_json(index, {"phase": context.request["phase"]})
    new_directory(path)
    request = {
        key: context.request[key]
        for key in (
            "configuration",
            "identity",
            "environmentId",
            "newEnvironment",
            "wheels",
            "jobId",
            "planHash",
            "phase",
        )
    }
    intent = {
        "jobId": context.request["jobId"],
        "planHash": context.request["planHash"],
        "identity": context.identity,
        "phase": context.request["phase"],
        "sourceFingerprint": context.source_fingerprint,
        "prefixIdentity": inode,
        "argv": argv,
        "environment": environment,
        "request": request,
        "scripts": {
            name: hashlib.sha256(text.encode()).hexdigest()
            for name, text in {**helpers, "install_owner.py": helper_source}.items()
        },
    }
    # Persist launch intent before scripts or spawn. Any partial failure remains unknown.
    write_json(path / "intent.json", intent)
    replace_json(
        job / "last-phase.json",
        {
            "phase": request["phase"],
            "jobId": request["jobId"],
            "planHash": request["planHash"],
        },
    )
    replace_json(
        context.slot / "last-writer.json",
        {
            "jobId": request["jobId"],
            "planHash": request["planHash"],
            "identity": context.identity,
        },
    )
    mkdir(path / "code")
    for name, text in {**helpers, "install_owner.py": helper_source}.items():
        write_file(path / "code" / name, text.encode())
    for name, text in files.items():
        write_file(path / name, text.encode())
    for name in ("home", "pkgs", "envs", "tmp"):
        mkdir(path / name)
    write_file(path / "owner.log", b"")
    log = open_file(path / "owner.log", os.O_WRONLY | os.O_APPEND | os.O_NOFOLLOW, owned=True)
    try:
        subprocess.Popen(
            [
                sys.executable,
                "-I",
                "-S",
                "-B",
                str(path / "code" / "install_owner.py"),
                "--serve",
                str(path),
                "--writer-fd",
                str(writer_fd),
            ],
            pass_fds=(writer_fd,),
            stdin=subprocess.DEVNULL,
            stdout=log,
            stderr=log,
            start_new_session=True,
            close_fds=True,
            env={"PATH": "/usr/bin:/bin", "PYTHONDONTWRITEBYTECODE": "1"},
        )
    except OSError:
        # Exec result unknown to caller; never remove intent or retry this phase.
        pass
    finally:
        os.close(log)
    return inspect_phase(context, job)


def dispatch(request):
    if not isinstance(request, dict):
        fail("INSTALL_REQUEST_INVALID")
    action = request.get("action")
    if action not in {
        "snapshot",
        "reserve",
        "allocate",
        "mark-owned",
        "mark-ready",
        "verify",
        "run",
        "inspect",
        "cancel",
        "release",
    }:
        fail("INSTALL_ACTION_INVALID")
    fields = {
        "action",
        "configuration",
        "identity",
        "wheels",
        "environmentId",
        "newEnvironment",
        "nonce",
    }
    allowed = set(fields)
    if action != "snapshot":
        allowed |= {"jobId", "planHash"}
    if action in {"run", "inspect", "cancel"}:
        allowed.add("phase")
    if action == "run":
        allowed |= {"argv", "environment", "helpers", "helperSource", "files"}
    if (
        not fields <= set(request)
        or not set(request) <= allowed
        or not isinstance(request["nonce"], str)
        or not 1 <= len(request["nonce"]) <= 256
    ):
        fail("INSTALL_REQUEST_INVALID")
    context = Context(request)
    if action == "snapshot":
        result = snapshot(context)
    elif action == "reserve":
        result = reserve(context)
    else:
        job, claim = context.job()
        if action in {"inspect", "cancel"}:
            phase = selected_phase(context, job)
            if phase is not None:
                context.request = dict(context.request, phase=phase)
            path = phase_path(context, job) if phase is not None else None
            if action == "cancel" and path is not None and path.exists():
                intent_check(context, path)
                if not (path / "install-cancel.request.json").exists():
                    write_json(
                        path / "install-cancel.request.json",
                        {
                            "phase": phase,
                            "jobId": claim["jobId"],
                            "planHash": claim["planHash"],
                        },
                    )
            result = inspect_phase(context, job)
        else:
            pending = (
                settling_owner(context, job)
                if action in {"verify", "release", "mark-ready"}
                else None
            )
            with lock(context.slot / ".writer.lock", pending=pending) as writer_fd:
                if (job / "closed.json").exists() and action != "release":
                    fail("INSTALL_CLAIM_CLOSED")
                if action == "allocate":
                    context.authorized()
                    if not context.new:
                        fail("INSTALL_ALLOCATION_INVALID")
                    mkdir(context.root / "training-environments")
                    if not context.prefix.exists():
                        new_directory(context.prefix)
                        info = directory(context.prefix, owned=True)
                        write_json(
                            context.slot / "allocation.json",
                            {
                                "environmentId": context.env,
                                "prefixIdentity": [info.st_dev, info.st_ino],
                                "identity": context.identity,
                            },
                        )
                    inode = context.allocation()
                    result = {"ack": True, "prefixIdentity": inode}
                elif action in {"mark-owned", "mark-ready", "verify"}:
                    allocation_missing = not (context.slot / "allocation.json").exists()
                    if action == "verify" and context.new and allocation_missing:
                        inode, _ = context.prefix_info(allow_empty=True)
                        if inode is not None:
                            fail("INSTALL_PREFIX_REPLACED")
                    else:
                        inode = context.allocation()
                    used = occupied(context, job)
                    if used > context.budget:
                        fail("INSTALL_DISK_BUDGET_EXCEEDED")
                    if action == "mark-owned":
                        context.authorized()
                        marker = {"ownedByEasyAI": True, "environmentId": context.env}
                        if not (context.prefix / ".easyai-owned.json").exists():
                            write_json(context.prefix / ".easyai-owned.json", marker)
                        elif encoded(read_json(context.prefix / ".easyai-owned.json")) != encoded(
                            marker
                        ):
                            fail("INSTALL_ENVIRONMENT_NOT_OWNED")
                        if context.new:
                            origin = context.prefix / ".easyai-install-origin.json"
                            if not origin.exists():
                                write_json(origin, claim)
                            elif read_json(origin) != claim:
                                fail("INSTALL_CLAIM_MISMATCH")
                    else:
                        context.prefix_info(allow_empty=action == "verify" and context.new)
                    if action == "mark-ready":
                        context.authorized()
                        ready = {
                            "prefixIdentity": inode,
                            "jobId": claim["jobId"],
                            "planHash": claim["planHash"],
                            "identity": context.identity,
                        }
                        if not (job / "ready.json").exists():
                            write_json(job / "ready.json", ready)
                        elif read_json(job / "ready.json") != ready:
                            fail("INSTALL_READY_RECEIPT_CONFLICT")
                        replace_json(context.slot / "ready.json", ready)
                    result = {"ack": True, "prefixIdentity": inode, "usedBytes": used}
                elif action == "run":
                    result = run_phase(context, job, writer_fd)
                elif action == "release":
                    workspace = context.root / "install-processes" / job.name
                    indexes = {entry.name for entry in (job / "phases").iterdir()}
                    physical = (
                        {entry.name for entry in workspace.iterdir()}
                        if workspace.exists()
                        else set()
                    )
                    if physical != indexes:
                        fail("INSTALL_PHASE_UNCONFIRMED")
                    for entry in (job / "phases").iterdir():
                        context.request = dict(request, phase=identifier(entry.name))
                        if not inspect_phase(context, job)["quiescent"]:
                            fail("INSTALL_PHASE_UNCONFIRMED")
                    inode, _ = context.prefix_info(allow_empty=True)
                    if inode is not None:
                        inode = context.allocation()
                    closed = {
                        "jobId": claim["jobId"],
                        "planHash": claim["planHash"],
                        "identity": context.identity,
                        "prefixIdentity": inode,
                    }
                    if not (job / "closed.json").exists():
                        write_json(job / "closed.json", closed)
                    elif read_json(job / "closed.json") != closed:
                        fail("INSTALL_CLAIM_MISMATCH")
                    result = {"ack": True, "prefixIdentity": inode}
                else:
                    fail("INSTALL_ACTION_INVALID")
    common = {
        "nonce": request.get("nonce"),
        "root": str(context.root),
        "prefix": str(context.prefix),
        "environmentId": context.env,
    }
    if action != "snapshot":
        common.update(jobId=request["jobId"], planHash=request["planHash"])
    return {**common, **result}


def load_module(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        fail("INSTALL_HELPER_INVALID")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def serve(path, writer_fd=None):
    path = absolute(path)
    directory(path, owned=True)
    intent = read_json(path / "intent.json")
    request = intent["request"]
    context = Context(request)
    job, _ = context.job()
    if path != phase_path(context, job):
        fail("INSTALL_PHASE_MISMATCH")
    with inherited_lock(context.slot / ".writer.lock", writer_fd):
        if (job / "closed.json").exists():
            fail("INSTALL_CLAIM_CLOSED")
        context.authorized()
        intent_check(context, path)
        if not context.new:
            context.prefix_info()
        if context.allocation() != intent["prefixIdentity"]:
            fail("INSTALL_PREFIX_REPLACED")
        for name, checksum in intent["scripts"].items():
            if name not in {"install_owner.py", "managed.py", "portable_journal.py"}:
                fail("INSTALL_HELPER_INVALID")
            if hashlib.sha256(file_read(path / "code" / name)[0]).hexdigest() != checksum:
                fail("INSTALL_HELPER_CHANGED")
        # Source/space were revalidated by Context above; include all phase caches in the budget.
        if occupied(context, job) > context.budget:
            fail("INSTALL_DISK_BUDGET_EXCEEDED")
        write_json(path / "serve.claim.json", {"phase": request["phase"]})
        managed = load_module(path / "code" / "managed.py", "easyai_install_managed")
        journal = load_module(path / "code" / "portable_journal.py", "easyai_install_journal")
        process = managed.ManagedProcess(
            path,
            request["phase"],
            intent["argv"],
            context.prefix,
            intent["environment"],
            journal_factory=journal.PortableJournal,
            max_log_bytes=1024 * 1024,
            inherit_environment=False,
        )

        def cancellation_requested():
            cancel = path / "install-cancel.request.json"
            return cancel.exists() and read_json(cancel) == {
                "phase": request["phase"],
                "jobId": request["jobId"],
                "planHash": request["planHash"],
            }

        # Exclusive serve claim + writer ownership prove no child has been dispatched.
        # Check immediately before the actual spawn boundary, not only in the poll loop.
        if cancellation_requested():
            publish_status(
                path / "status.json",
                {
                    "phase": request["phase"],
                    "phaseRoot": str(path),
                    "jobId": request["jobId"],
                    "planHash": request["planHash"],
                    "outcome": "cancelled",
                    "quiescent": True,
                    "events": [],
                    "dispatched": False,
                },
            )
            return
        cancelled, fault, outcome, quiet = False, False, "unknown", False
        deadline = time.monotonic() + context.config["seconds"]
        try:
            process.start()
            while True:
                if cancellation_requested():
                    cancelled = True
                    process.request_cancel()
                with process.snapshot() as (_, done, _):
                    if done:
                        break
                if time.monotonic() >= deadline or occupied(context, job) > context.budget:
                    fault = True
                    process.request_cancel()
                time.sleep(0.05)
        except BaseException:
            fault = True
        finally:
            try:
                process.close()
                quiet = process.quiescent
                with process.snapshot() as (state, done, _):
                    if quiet and done:
                        outcome = (
                            "failed"
                            if fault
                            else "cancelled"
                            if cancelled
                            else "completed"
                            if state == "COMPLETED"
                            else "failed"
                        )
                    else:
                        quiet = False
                events = [item.value for item in process.events()]
                # Never expose unbounded output in RPC; the managed journal already caps lines.
                if len(encoded(events)) > MAX_JSON // 2:
                    events, outcome = [], "failed" if quiet else "unknown"
                publish_status(
                    path / "status.json",
                    {
                        "phase": request["phase"],
                        "phaseRoot": str(path),
                        "jobId": request["jobId"],
                        "planHash": request["planHash"],
                        "outcome": outcome,
                        "quiescent": quiet,
                        "events": events,
                        "dispatched": True,
                    },
                )
            except BaseException:
                # Missing/partial terminal evidence remains unknown; no cleanup or fabricated exit.
                pass


def main():
    try:

        class Parser(argparse.ArgumentParser):
            def error(self, message):
                fail("INSTALL_ARGUMENT_INVALID")

        parser = Parser(add_help=False)
        parser.add_argument("--serve")
        parser.add_argument("--writer-fd", type=int)
        args = parser.parse_args()
        if args.serve:
            serve(args.serve, args.writer_fd)
            return
        if args.writer_fd is not None:
            fail("INSTALL_ARGUMENT_INVALID")
        raw = sys.stdin.buffer.read(MAX_JSON + 1)
        if len(raw) > MAX_JSON:
            fail("INSTALL_REQUEST_LIMIT")
        result = dispatch(decoded(raw))
    except Exception as error:
        code = str(error) if type(error) is ValueError else "INSTALL_OWNER_FAILED"
        if not re.fullmatch("INSTALL_[A-Z_]{1,80}", code):
            code = "INSTALL_OWNER_FAILED"
        result = {"error": {"code": code}}
    sys.stdout.buffer.write(encoded(result) + b"\n")


if __name__ == "__main__":
    main()
