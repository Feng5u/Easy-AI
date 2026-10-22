"""Cleanup ownership contracts only; fake close failures are not native acceptance."""

import pytest

from easyai.security import windows_host_keys as native


@pytest.mark.parametrize("failure", ["lock", "directory"])
def test_failed_close_always_attempts_both_and_retains_uncertain_owner(
    tmp_path, monkeypatch, failure
):
    calls = []
    monkeypatch.setattr(native, "_FAILED_CLEANUP", [])

    class Lock:
        fd = 123

        def close(self):
            calls.append("lock")
            self.fd = None
            if failure == "lock":
                raise OSError("injected close failure")

    class Directory:
        _chain = [("held", 321, None)]

        def __init__(self, path):
            calls.append("open")

        def identity(self):
            return 1, b"file-id"

        def verify(self):
            pass

        def writer_lock(self, name):
            return Lock()

        def close(self):
            calls.append("directory")
            self._chain = []
            if failure == "directory":
                raise OSError("injected close failure")

    monkeypatch.setattr(native, "WindowsDirectory", Directory)
    store = native.WindowsTrustStore.__new__(native.WindowsTrustStore)
    store.root, store.identity = tmp_path, (1, b"file-id")
    with pytest.raises(ValueError, match="SSH_TRUST_CLEANUP_UNCONFIRMED"):
        with store.transaction(exclusive=True):
            pass
    assert calls == ["open", "lock", "directory"]
    assert len(native._FAILED_CLEANUP) == 1
    owner, chain, original_fd = native._FAILED_CLEANUP[0]
    if failure == "lock":
        assert isinstance(owner, Lock) and original_fd == 123
    else:
        assert isinstance(owner, Directory) and chain == (("held", 321, None),)
    with pytest.raises(ValueError, match="SSH_TRUST_CLEANUP_UNCONFIRMED"):
        with store.transaction():
            pytest.fail("Uncertain cleanup must never permit another operation")
    with pytest.raises(ValueError, match="SSH_TRUST_CLEANUP_UNCONFIRMED"):
        native.WindowsTrustStore(tmp_path / "another")
    assert calls == ["open", "lock", "directory"]
