"""Real POSIX file/lock contracts and import rejection, never Windows acceptance."""

import os
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace

import pytest

import easyai.security.remote_cache as storage


@pytest.fixture
def directory(tmp_path):
    if os.name != "posix":
        pytest.skip("Native POSIX storage contract; Windows backend is not implemented")
    root = tmp_path / "private"
    root.mkdir(mode=0o700)
    value = storage.local_directory(root)
    try:
        yield value
    finally:
        value.close()


def write(directory, name, raw):
    with os.fdopen(directory.open_file(name, "exclusive"), "wb") as output:
        output.write(raw)
        output.flush()
        directory.sync_file(output.fileno())


@pytest.mark.parametrize("name", ["", ".", "..", "../x", "/outside", "x/y", "C:x", "x\\y", "x\0y"])
def test_store_components_never_become_paths(directory, name):
    with pytest.raises(ValueError, match="COMPONENT_INVALID"):
        directory.open_file(name, "update")
    assert directory.names() == []


@pytest.mark.parametrize("kind", ["symlink", "fifo", "directory", "writable"])
def test_store_rejects_nonregular_and_unsafe_files_without_waiting(directory, kind):
    path = directory.path / "unsafe"
    if kind == "symlink":
        path.symlink_to(directory.path.parent / "outside")
    elif kind == "fifo":
        os.mkfifo(path, 0o600)
    elif kind == "directory":
        path.mkdir(mode=0o700)
    else:
        path.write_bytes(b"untouched")
        path.chmod(0o666)
    with pytest.raises((ValueError, OSError)):
        directory.open_file("unsafe", "update")
    if kind == "writable":
        assert path.read_bytes() == b"untouched" and path.stat().st_mode & 0o022


def test_held_directory_cannot_follow_replacement(directory):
    old = directory.path.with_name("held-old")
    directory.path.rename(old)
    directory.path.mkdir(mode=0o700)
    with pytest.raises(ValueError, match="REPLACED"):
        directory.open_file("new-file", "exclusive")
    assert not (directory.path / "new-file").exists() and not (old / "new-file").exists()


def test_symlink_child_and_unsafe_permissions_are_not_repaired(directory, tmp_path):
    outside = tmp_path / "outside"
    outside.mkdir(mode=0o700)
    (directory.path / "child").symlink_to(outside, target_is_directory=True)
    with pytest.raises((ValueError, OSError)):
        directory.child("child", create=True)
    assert list(outside.iterdir()) == []
    (directory.path / "child").unlink()
    unsafe = directory.path / "unsafe"
    unsafe.mkdir(mode=0o777)
    unsafe.chmod(0o777)
    with pytest.raises(ValueError, match="DIRECTORY_UNSAFE"):
        directory.child("unsafe", create=True)
    assert unsafe.stat().st_mode & 0o777 == 0o777


def test_nonreplace_publication_preserves_existing_bytes_and_symlink(directory):
    write(directory, "source", b"new")
    write(directory, "target", b"old")
    with pytest.raises(FileExistsError):
        directory.publish("source", "target")
    assert (directory.path / "target").read_bytes() == b"old"
    (directory.path / "target").unlink()
    (directory.path / "target").symlink_to("source")
    with pytest.raises((ValueError, OSError)):
        directory.publish("source", "target", replace=True)
    assert (directory.path / "target").is_symlink()
    assert (directory.path / "source").read_bytes() == b"new"


def test_checkpoint_publication_orders_file_flush_rename_directory_flush(directory, monkeypatch):
    operations = []
    original_sync, original_replace = os.fsync, os.replace

    def sync(fd):
        operations.append("directory" if fd == directory._fd else "file")
        return original_sync(fd)

    def replace(*args, **kwargs):
        operations.append("rename")
        return original_replace(*args, **kwargs)

    monkeypatch.setattr(os, "fsync", sync)
    monkeypatch.setattr(os, "replace", replace)
    write(directory, "temporary", b"committed")
    directory.publish("temporary", "checkpoint", replace=True)
    assert operations == ["file", "rename", "directory"]
    assert (directory.path / "checkpoint").read_bytes() == b"committed"


def test_directory_flush_failure_never_acknowledges_publication(directory, monkeypatch):
    write(directory, "temporary", b"possibly published")

    def fail(fd):
        raise OSError("synthetic durable directory failure")

    monkeypatch.setattr(os, "fsync", fail)
    with pytest.raises(OSError):
        directory.publish("temporary", "checkpoint", replace=True)
    # Publication may have happened. The caller must preserve uncertainty, not retry start.
    assert (directory.path / "checkpoint").read_bytes() == b"possibly published"


def test_kernel_writer_lock_is_permanent_and_excludes_another_process(directory):
    lock = directory.writer_lock("writer")
    identity = (directory.path / "writer").stat().st_ino
    code = """
import sys
from pathlib import Path
from easyai.security.remote_cache import local_directory
root = local_directory(Path(sys.argv[1]))
try:
    try:
        lock = root.writer_lock('writer')
    except BlockingIOError:
        print('held')
    else:
        print('acquired')
        lock.close()
finally:
    root.close()
"""
    try:
        child = subprocess.run(
            [sys.executable, "-c", code, str(directory.path)],
            capture_output=True,
            timeout=3,
            check=True,
        )
        assert child.stdout.strip() == b"held"
        lock.verify()
    finally:
        lock.close()
    assert (directory.path / "writer").stat().st_ino == identity
    child = subprocess.run(
        [sys.executable, "-c", code, str(directory.path)],
        capture_output=True,
        timeout=3,
        check=True,
    )
    assert child.stdout.strip() == b"acquired"
    assert (directory.path / "writer").stat().st_ino == identity


def test_native_lock_import_is_lazy_in_a_fresh_interpreter():
    code = """
import builtins
original = builtins.__import__
def guarded(name, *args, **kwargs):
    if name == 'fcntl' and args and args[0].get('__name__', '').startswith('easyai.'):
        raise AssertionError('native POSIX dependency imported before platform gate')
    return original(name, *args, **kwargs)
builtins.__import__ = guarded
import easyai.services.remote_bundle
import easyai.services.remote_artifacts
import easyai.runners.ssh
print('imported')
"""
    child = subprocess.run([sys.executable, "-c", code], capture_output=True, timeout=3)
    assert child.returncode == 0, child.stderr.decode()
    assert child.stdout.strip() == b"imported"


def test_unverified_platform_refuses_before_any_local_or_native_access(monkeypatch):
    # Inject only the capability provider; this is deliberately NOT a Windows OS fixture.
    def forbidden(*args, **kwargs):
        pytest.fail("Unsupported backend must not touch storage")

    monkeypatch.setattr(storage, "os", SimpleNamespace(name="nt", open=forbidden))
    with pytest.raises(ValueError, match="PLATFORM_UNVERIFIED"):
        storage.local_directory(Path("/synthetic"))
