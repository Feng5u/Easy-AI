"""Native enum policy/selector checks; these do not establish Windows acceptance."""

import ctypes as C
from pathlib import Path
import struct
from types import SimpleNamespace

import pytest

from easyai.security import remote_cache
from easyai.security.windows_store import IoStatus, NativeWindowsApi


def page(name):
    raw = name.encode("utf-16-le")
    return struct.pack("<III", 0, 0, len(raw)) + raw


def enumeration(pages):
    api = NativeWindowsApi.__new__(NativeWindowsApi)
    calls = []

    def query(handle, event, apc, context, io, buffer, size, kind, single, mask, restart):
        calls.append(restart)
        status = C.cast(io, C.POINTER(IoStatus)).contents
        if not pages:
            status.StatusOrPointer = 0x80000006
            return 0x80000006
        raw = pages.pop(0)
        status.StatusOrPointer, status.Information = 0, len(raw)
        C.memmove(buffer, raw, min(size, len(raw)))
        return 0

    api.nt = SimpleNamespace(NtQueryDirectoryFile=query)
    return api, calls


def test_native_enumeration_exact_limit_and_explicit_end_receipt():
    api, calls = enumeration([page("."), page(".."), page("中文.bin")])
    assert api.names(123, limit=1) == ["中文.bin"]
    assert calls == [1, 0, 0, 0]


@pytest.mark.parametrize(
    "pages",
    [
        [page("first"), page("second")],
        [page("."), page(".")],
        [page("File"), page("file")],
        [b"short"],
        [struct.pack("<III", 0, 0, 3) + b"abc"],
        [page("..\\outside")],
    ],
)
def test_native_enumeration_rejects_limits_duplicates_and_malformed_records(pages):
    api, calls = enumeration(pages)
    with pytest.raises(ValueError):
        api.names(123, limit=1)
    assert len(calls) <= 2


def test_windows_selector_stays_closed_without_internal_native_acceptance(monkeypatch):
    monkeypatch.setattr(remote_cache, "os", SimpleNamespace(name="nt"))
    monkeypatch.setattr(remote_cache, "platform", SimpleNamespace(machine=lambda: "AMD64"))
    monkeypatch.setattr(remote_cache, "WINDOWS_NATIVE_CACHE_VERIFIED", False)
    with pytest.raises(ValueError, match="REMOTE_CACHE_PLATFORM_UNVERIFIED"):
        remote_cache.local_directory(Path("C:/private"))
    with pytest.raises(ValueError, match="REMOTE_CACHE_PLATFORM_UNVERIFIED"):
        remote_cache.require_local_cache()
