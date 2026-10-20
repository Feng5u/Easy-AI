"""Manifest-only inspection and missing-file upload to an exact owned slot."""

import errno
import hashlib
from pathlib import PurePosixPath
import threading
from typing import Any, Callable

from easyai.services.data_transfer_errors import TransferFailure
from easyai.services.data_transfer_record import UploadIntent
from easyai.services.data_transfer_source import TransferSource
from easyai.services.data_transfer_transport import DataUploadTransport
from easyai.services.remote_artifacts import _encoded


def missing(
    sftp: Any,
    transport: DataUploadTransport,
    intent: UploadIntent,
    attempts: list[str],
    check: Callable[[], None],
) -> tuple[str, ...]:
    managed = str(PurePosixPath(intent.root).parent)
    try:
        sftp.lstat(managed)
    except OSError as error:
        if error.errno == errno.ENOENT:
            # A never-published slot can be created only by the later confirmed send.
            transport.directory(sftp, intent.home, intent.uid, check)
            return tuple(f.path for f in intent.files)
        raise
    reader = transport.directory(sftp, managed, intent.uid, check)
    owner = _encoded({"protocolVersion": 1, "projectId": intent.project_id, "uid": intent.uid})
    if reader.record(".easyai-owner.json") != owner:
        raise TransferFailure("DATA_TRANSFER_TARGET_UNOWNED")
    try:
        sftp.lstat(intent.root)
    except OSError as error:
        if error.errno == errno.ENOENT:
            return tuple(f.path for f in intent.files)
        raise
    reader = transport.directory(sftp, intent.root, intent.uid, check)
    if reader.record(".easyai-transfer.json") != intent.raw():
        raise TransferFailure("DATA_TRANSFER_RECOVERY_INVALID")
    expected = {f.path for f in intent.files}
    directories = set(intent.directories)
    partials = {
        str(PurePosixPath(f.path).parent / (".part-" + attempt + "-" + str(index)))
        for attempt in attempts
        for index, f in enumerate(intent.files)
    }
    partials |= {".complete-" + attempt + ".part" for attempt in attempts}
    allowed = expected | partials | {".easyai-transfer.json", ".easyai-complete.json"}
    count = 0

    def walk(prefix: str) -> None:
        nonlocal count
        transport.directory(sftp, intent.root + ("/" + prefix if prefix else ""), intent.uid, check)
        iterator = sftp.listdir_iter(intent.root + ("/" + prefix if prefix else ""), read_aheads=1)
        try:
            for entry in iterator:
                check()
                count += 1
                name = entry.filename
                if (
                    count > 8192
                    or type(name) is not str
                    or name in ("", ".", "..")
                    or any(c in name for c in "/\\:")
                ):
                    raise TransferFailure("DATA_TRANSFER_RECOVERY_INVALID")
                relative = prefix + "/" + name if prefix else name
                info = sftp.lstat(intent.root + "/" + relative)
                if relative in directories:
                    reader._stat(info, True)
                    walk(relative)
                elif relative in allowed:
                    reader._stat(info, False)
                    if info.st_size > 100 * 1024 * 1024:
                        raise TransferFailure("DATA_TRANSFER_SOURCE_LIMIT")
                else:
                    raise TransferFailure("DATA_TRANSFER_RECOVERY_INVALID")
        finally:
            iterator.close()

    walk("")
    result = []
    for record in intent.files:
        check()
        try:
            reader._parents(record.path)
        except OSError as error:
            if error.errno == errno.ENOENT:
                result.append(record.path)
                continue
            raise
        digest = hashlib.sha256()
        reader.read(record.path, record.bytes, digest.update)
        if digest.hexdigest() != record.sha256:
            raise TransferFailure("DATA_TRANSFER_HASH_MISMATCH")
    try:
        completion = reader.record(".easyai-complete.json")
    except OSError as error:
        if error.errno != errno.ENOENT:
            raise
    else:
        if result or completion != intent.completion():
            raise TransferFailure("DATA_TRANSFER_RECOVERY_INVALID")
    return tuple(result)


def inspect(
    transport: DataUploadTransport,
    intent: UploadIntent,
    attempts: list[str],
    cancel: threading.Event,
    seconds: int,
    authority: Callable[[], None],
) -> tuple[str, ...]:
    with transport.connection(cancel, seconds) as (sftp, check_transport):

        def check() -> None:
            check_transport()
            authority()

        if sftp.normalize(".") != intent.home:
            raise TransferFailure("DATA_TRANSFER_HOME_CHANGED")
        return missing(sftp, transport, intent, attempts, check)


def send(
    transport: DataUploadTransport,
    source: TransferSource,
    intent: UploadIntent,
    attempt: str,
    attempts: list[str],
    expected_missing: tuple[str, ...],
    cancel: threading.Event,
    seconds: int,
    progress: Callable[[str, int, int], None],
    authority: Callable[[], None],
) -> None:
    with transport.connection(cancel, seconds) as (sftp, check_transport):

        def check() -> None:
            check_transport()
            authority()

        if sftp.normalize(".") != intent.home:
            raise TransferFailure("DATA_TRANSFER_HOME_CHANGED")
        if missing(sftp, transport, intent, attempts, check) != expected_missing:
            raise TransferFailure("DATA_TRANSFER_RECOVERY_INVALID")
        managed = transport.managed(
            sftp, intent.project_id, attempt, intent.home, intent.uid, check
        )
        try:
            sftp.lstat(intent.root)
        except OSError as error:
            if error.errno != errno.ENOENT:
                raise
            staging = managed + "/.slot-init-" + attempt
            check()
            sftp.mkdir(staging, mode=0o700)
            transport.directory(sftp, staging, intent.uid, check)
            transport.write_record(sftp, staging + "/.easyai-transfer.json", intent.raw(), check)
            if (
                transport.directory(sftp, staging, intent.uid, check).record(
                    ".easyai-transfer.json"
                )
                != intent.raw()
            ):
                raise TransferFailure("DATA_TRANSFER_RECOVERY_INVALID")
            check()
            transport.directory(sftp, managed, intent.uid, check)
            sftp.rename(staging, intent.root)
        transport.directory(sftp, intent.root, intent.uid, check)
        for relative in intent.directories:
            check()
            path = intent.root + "/" + relative
            try:
                sftp.lstat(path)
            except OSError as error:
                if error.errno != errno.ENOENT:
                    raise
                sftp.mkdir(path, mode=0o700)
            transport.directory(sftp, path, intent.uid, check)
        source_by_name = {f.name: f for f in source.files}
        for index, record in enumerate(intent.files):
            if record.path not in expected_missing:
                continue
            temporary = str(
                PurePosixPath(record.path).parent / (".part-" + attempt + "-" + str(index))
            )
            digest, count = hashlib.sha256(), 0
            with source.open(source_by_name[record.path], check) as local:
                with sftp.open(intent.root + "/" + temporary, "wx", bufsize=0) as output:
                    output.chmod(0o600)
                    while raw := local.read(65536):
                        check()
                        count += len(raw)
                        if count > record.bytes:
                            raise TransferFailure("DATA_TRANSFER_SOURCE_CHANGED")
                        output.write(raw)
                        digest.update(raw)
                        progress("sent", len(raw), 0)
                    output.flush()
            if count != record.bytes or digest.hexdigest() != record.sha256:
                raise TransferFailure("DATA_TRANSFER_SOURCE_CHANGED")
            reader = transport.directory(sftp, intent.root, intent.uid, check)
            received = hashlib.sha256()
            reader.read(temporary, record.bytes, received.update)
            if received.hexdigest() != record.sha256:
                raise TransferFailure("DATA_TRANSFER_HASH_MISMATCH")
            check()
            sftp.rename(intent.root + "/" + temporary, intent.root + "/" + record.path)
        progress("verifying", 0, 0)
        reader = transport.directory(sftp, intent.root, intent.uid, check)
        for record in intent.files:
            digest = hashlib.sha256()
            reader.read(record.path, record.bytes, digest.update)
            if digest.hexdigest() != record.sha256:
                raise TransferFailure("DATA_TRANSFER_HASH_MISMATCH")
            progress("verified", record.bytes, 1)
        try:
            complete = reader.record(".easyai-complete.json")
        except OSError as error:
            if error.errno != errno.ENOENT:
                raise
            temporary = ".complete-" + attempt + ".part"
            transport.write_record(sftp, intent.root + "/" + temporary, intent.completion(), check)
            if reader.record(temporary) != intent.completion():
                raise TransferFailure("DATA_TRANSFER_HASH_MISMATCH")
            check()
            sftp.rename(intent.root + "/" + temporary, intent.root + "/.easyai-complete.json")
            complete = reader.record(".easyai-complete.json")
        if complete != intent.completion():
            raise TransferFailure("DATA_TRANSFER_RECOVERY_INVALID")
        check()
