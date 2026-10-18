"""Windows policy/ABI/call ownership contracts on Linux; no native acceptance."""

import ctypes as C
import os
from pathlib import Path
import struct
import sys
from types import SimpleNamespace

import pytest

from easyai.security.windows_store import (
    Ace,
    AttributeTag,
    FileId,
    Identity,
    Info,
    IoStatus,
    NativeWindowsApi,
    ObjectAttributes,
    Overlapped,
    StandardInfo,
    UnicodeString,
    WindowsDirectory,
    component,
    rename_argument,
    unicode_argument,
    validate_acl,
)

USER = "S-1-5-21-1000"
OTHER = "S-1-5-21-2000"


def test_x64_abi_sizes_offsets_use_windows_widths_even_on_linux():
    assert C.sizeof(C.c_void_p) == 8
    assert C.sizeof(UnicodeString) == 16 and UnicodeString.Buffer.offset == 8
    assert C.sizeof(ObjectAttributes) == 48 and ObjectAttributes.RootDirectory.offset == 8
    assert ObjectAttributes.Attributes.offset == 24
    assert C.sizeof(IoStatus) == 16 and IoStatus.Information.offset == 8
    assert C.sizeof(FileId) == 24 and FileId.Identifier.offset == 8
    assert C.sizeof(AttributeTag) == 8 and C.sizeof(StandardInfo) == 24
    assert StandardInfo.DeletePending.offset == 20 and C.sizeof(Overlapped) == 32


def test_utf16_lengths_and_rename_offsets_are_bytes_without_implicit_padding():
    buffer, text = unicode_argument("测试 🧪")
    raw = "测试 🧪".encode("utf-16-le")
    assert text.Length == len(raw) and text.MaximumLength == len(raw) + 2
    assert C.string_at(text.Buffer, text.Length) == raw and buffer[-1] == 0
    payload = rename_argument(0x123456789ABCDEF0, "缓存.json", True)
    assert struct.unpack_from("<B7xQI", payload) == (
        1,
        0x123456789ABCDEF0,
        len("缓存.json".encode("utf-16-le")),
    )
    assert payload[20:] == "缓存.json".encode("utf-16-le")


@pytest.mark.parametrize(
    "name", ["CON", "nul.txt", "COM1", "LPT9.log", "x.", "x ", "..", "x:y", "a/b", "a\\b"]
)
def test_windows_components_reject_device_aliases_streams_and_normalization(name):
    with pytest.raises(ValueError):
        component(name)


@pytest.mark.parametrize(
    "mask", [2, 4, 0x10, 0x40, 0x100, 0x10000, 0x40000, 0x80000, 0x10000000, 0x40000000]
)
def test_untrusted_write_grants_never_pass_final_acl(mask):
    with pytest.raises(ValueError, match="UNSAFE"):
        validate_acl(USER, [Ace(0, 0, mask, OTHER)], USER, final=True)


def test_acl_trusted_owner_readonly_groups_and_ancestor_add_child_policy():
    validate_acl(USER, [Ace(0, 0, 0x1F01FF, USER), Ace(0, 0, 0x120089, OTHER)], USER, final=True)
    validate_acl("S-1-5-18", [Ace(0, 0, 4, OTHER)], USER, final=False)
    for owner, aces in [(OTHER, []), (USER, None), (USER, [Ace(5, 0, 0, USER)])]:
        with pytest.raises(ValueError):
            validate_acl(owner, aces, USER, final=True)
    # DENY does not justify an unsafe explicit allow; unknown ACEs fail closed.
    with pytest.raises(ValueError):
        validate_acl(USER, [Ace(1, 0, 2, OTHER), Ace(0, 0, 2, OTHER)], USER, final=True)


class RootApi:
    def __init__(self, failure):
        self.closed = []
        self.failure = failure

    def root(self, anchor):
        assert anchor == "C:\\"
        return 100

    def info(self, handle):
        if self.failure == "info":
            raise OSError("synthetic native info failure")
        return Info(Identity(1, b"r" * 16), 0x400 if self.failure == "reparse" else 0x10, 0, True)

    def security(self, handle, *, final):
        if self.failure == "security":
            raise ValueError("WINDOWS_CACHE_SECURITY_UNSAFE")

    def close(self, handle):
        self.closed.append(handle)


@pytest.mark.parametrize("failure", ["info", "security", "reparse"])
def test_root_validation_failure_closes_unadopted_handle_once(failure):
    api = RootApi(failure)
    with pytest.raises((OSError, ValueError)):
        WindowsDirectory(Path("C:/private"), api=api)
    assert api.closed == [100]


def test_native_relative_open_flags_and_unicode_are_exact_without_loading_dlls():
    api = NativeWindowsApi.__new__(NativeWindowsApi)
    observed = {}

    def create(
        out, access, attributes, io, allocation, attrs, shares, disposition, options, ea, size
    ):
        value = C.cast(attributes, C.POINTER(ObjectAttributes)).contents
        text = C.cast(value.ObjectName, C.POINTER(UnicodeString)).contents
        observed.update(
            parent=value.RootDirectory,
            flags=value.Attributes,
            name=C.string_at(text.Buffer, text.Length).decode("utf-16-le"),
            access=access,
            shares=shares,
            disposition=disposition,
            options=options,
        )
        C.cast(out, C.POINTER(C.c_void_p))[0] = 4321
        return 0

    api.nt = SimpleNamespace(NtCreateFile=create)
    assert api.child(1234, "文件.json", directory=False, create="create", write=True) == 4321
    assert observed["parent"] == 1234 and observed["flags"] == 0x40
    assert observed["name"] == "文件.json" and observed["disposition"] == 2
    assert observed["options"] & 0x200000 and observed["options"] & 0x40 and observed["options"] & 2
    assert observed["shares"] == 7


@pytest.mark.parametrize("failure", [None, "adopt", "inherit"])
def test_native_handle_to_crt_fd_ownership_closes_exactly_once(tmp_path, monkeypatch, failure):
    api = NativeWindowsApi.__new__(NativeWindowsApi)
    native_closed = []
    api.close = native_closed.append
    descriptor = os.open(tmp_path / "test-owned", os.O_CREAT | os.O_RDWR, 0o600)
    original_inherit = os.set_inheritable

    def adopt(handle, flags):
        assert handle == 1234
        if failure == "adopt":
            raise OSError("synthetic adoption failure")
        return descriptor

    def inheritable(fd, value):
        if failure == "inherit":
            raise OSError("synthetic inherit flag failure")
        original_inherit(fd, value)

    monkeypatch.setitem(sys.modules, "msvcrt", SimpleNamespace(open_osfhandle=adopt))
    monkeypatch.setattr(os, "O_BINARY", 0, raising=False)
    monkeypatch.setattr(os, "set_inheritable", inheritable)
    if failure:
        with pytest.raises(OSError):
            api.adopt(1234, readonly=False)
        assert native_closed == ([1234] if failure == "adopt" else [])
        if failure == "adopt":
            os.close(descriptor)  # Unrelated test fixture fd was never transferred.
        else:
            with pytest.raises(OSError):
                os.fstat(descriptor)
    else:
        assert api.adopt(1234, readonly=False) == descriptor
        assert not os.get_inheritable(descriptor) and not native_closed
        os.close(descriptor)


@pytest.mark.parametrize("operation", ["open", "publish", "remove", "names"])
@pytest.mark.parametrize("iosb", [0xC0000022, 0x103])
def test_native_receipts_require_completed_success_in_return_and_iosb(operation, iosb):
    api = NativeWindowsApi.__new__(NativeWindowsApi)
    closed = []
    api.close = closed.append

    def create(out, access, attributes, io, *args):
        C.cast(out, C.POINTER(C.c_void_p))[0] = 5432
        C.cast(io, C.POINTER(IoStatus)).contents.StatusOrPointer = iosb
        return 0

    def set_info(handle, io, *args):
        C.cast(io, C.POINTER(IoStatus)).contents.StatusOrPointer = iosb
        return 0

    def names(handle, event, apc, context, io, *args):
        C.cast(io, C.POINTER(IoStatus)).contents.StatusOrPointer = iosb
        return 0

    api.nt = SimpleNamespace(
        NtCreateFile=create,
        NtSetInformationFile=set_info,
        NtQueryDirectoryFile=names,
        RtlNtStatusToDosError=lambda _: 5,
    )
    with pytest.raises((ValueError, OSError)):
        if operation == "open":
            api.child(123, "record", directory=False)
        elif operation == "publish":
            api.publish(123, 456, "record", replace=True)
        elif operation == "remove":
            api.remove(123)
        else:
            api.names(123)
    assert closed == ([5432] if operation == "open" else [])


def test_owned_lock_cleanup_does_not_depend_on_namespace_revalidation(tmp_path):
    from easyai.security.windows_store import WindowsOwnerLock

    class Directory:
        def __init__(self):
            self.path = tmp_path
            self.fd = None
            self.verifies = 0
            self.api = SimpleNamespace(lock=lambda _: None, from_fd=lambda fd: fd)

        def open_file(self, name, access):
            flags = os.O_RDWR | (os.O_CREAT | os.O_EXCL if access == "exclusive" else 0)
            descriptor = os.open(self.path / name, flags, 0o600)
            if name == "owner":
                self.fd = descriptor
            return descriptor

        def sync_file(self, fd):
            os.fsync(fd)

        def publish(self, source, target):
            os.link(self.path / source, self.path / target)

        def remove(self, name, *, missing_ok=False):
            (self.path / name).unlink(missing_ok=missing_ok)

        def verify_file(self, name, fd):
            self.verifies += 1
            if self.verifies > 1:
                raise ValueError("WINDOWS_CACHE_FILE_REPLACED")

    (tmp_path / "owner").write_bytes(b"legacy-unverified")
    directory = Directory()
    lock = WindowsOwnerLock(directory, "owner")
    assert lock.fd is None and lock.reason == "PROJECT_LOCK_LEGACY_UNVERIFIED"
    assert directory.verifies == 1
    with pytest.raises(OSError):
        os.fstat(directory.fd)
