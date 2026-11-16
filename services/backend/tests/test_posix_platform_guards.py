"""Windows never enters POSIX-only I/O while both branches remain typechecked."""

import sys

import pytest

from easyai.security import host_keys, remote_cache
from easyai.services import install_runtime, owned_creation

pytestmark = pytest.mark.skipif(sys.platform != "win32", reason="Windows syscall guards")


def test_posix_cache_helpers_fail_before_touching_files(tmp_path):
    info = tmp_path.stat()
    for operation in (
        lambda: remote_cache.check_file(info),
        lambda: remote_cache._directory(info, final=True, anchor_uid=0),
        lambda: remote_cache.open_directory(tmp_path),
    ):
        with pytest.raises(ValueError, match="REMOTE_CACHE_PLATFORM_UNVERIFIED"):
            operation()


def test_posix_install_helpers_fail_before_touching_files(tmp_path):
    for operation in (
        lambda: owned_creation.sync_directory(tmp_path),
        lambda: install_runtime.protected(tmp_path),
        lambda: install_runtime.private_snapshot(tmp_path, 1),
    ):
        with pytest.raises(ValueError, match="INSTALL_PROFILE_PLATFORM_UNSUPPORTED"):
            operation()


def test_posix_host_key_reader_cannot_run_on_windows():
    store = object.__new__(host_keys.HostKeyStore)
    store._native_store = None
    with pytest.raises(ValueError, match="SSH_TRUST_PLATFORM_UNVERIFIED"):
        store._read_posix(-1)
    with pytest.raises(ValueError, match="SSH_TRUST_PLATFORM_UNVERIFIED"):
        with store._directory():
            pytest.fail("Windows must not enter the POSIX transaction")
