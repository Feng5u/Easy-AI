"""Experimental Windows x64/NTFS host storage. Production capability stays OFF.

Native calls are handle relative; no privilege changes, ACL repairs, shell or
path-based fallback. Linux policy/ABI tests do not validate these Windows calls.
"""

import ctypes as C
from dataclasses import dataclass
import errno
import os
from pathlib import Path, PureWindowsPath
import re
import struct
from typing import Any

from easyai.security.remote_cache import Access, LocalDirectory, LocalWriterLock, _name

U8, U16, U32, I32, U64, I64 = C.c_uint8, C.c_uint16, C.c_uint32, C.c_int32, C.c_uint64, C.c_int64
PTR = C.c_void_p
READ_CONTROL, SYNCHRONIZE, DELETE = 0x20000, 0x100000, 0x10000
REPARSE, DIRECTORY = 0x400, 0x10
TRUSTED = frozenset({"S-1-5-18", "S-1-5-32-544"})  # OS administrators are outside this boundary.


class UnicodeString(C.Structure):
    _fields_ = [("Length", U16), ("MaximumLength", U16), ("Buffer", PTR)]


class ObjectAttributes(C.Structure):
    _fields_ = [
        ("Length", U32),
        ("RootDirectory", PTR),
        ("ObjectName", PTR),
        ("Attributes", U32),
        ("SecurityDescriptor", PTR),
        ("SecurityQoS", PTR),
    ]


class IoStatus(C.Structure):
    _fields_ = [("StatusOrPointer", PTR), ("Information", C.c_size_t)]


class FileId(C.Structure):
    _fields_ = [("Volume", U64), ("Identifier", U8 * 16)]


class AttributeTag(C.Structure):
    _fields_ = [("Attributes", U32), ("Tag", U32)]


class StandardInfo(C.Structure):
    _fields_ = [
        ("Allocation", I64),
        ("Size", I64),
        ("Links", U32),
        ("DeletePending", U8),
        ("Directory", U8),
    ]


class Overlapped(C.Structure):
    _fields_ = [
        ("Internal", C.c_size_t),
        ("InternalHigh", C.c_size_t),
        ("Offset", U32),
        ("OffsetHigh", U32),
        ("Event", PTR),
    ]


class AclHeader(C.Structure):
    _fields_ = [
        ("Revision", U8),
        ("Reserved", U8),
        ("Size", U16),
        ("Count", U16),
        ("Reserved2", U16),
    ]


@dataclass(frozen=True)
class Ace:
    kind: int
    flags: int
    mask: int
    sid: str


@dataclass(frozen=True)
class Identity:
    volume: int
    file_id: bytes


@dataclass(frozen=True)
class Info:
    identity: Identity
    attributes: int
    size: int
    directory: bool


def component(value: str) -> str:
    value = _name(value)
    if value.endswith((".", " ")) or re.fullmatch(
        r"(?i)(CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])(?:\..*)?", value
    ):
        raise ValueError("WINDOWS_CACHE_COMPONENT_INVALID")
    return value


def validate_acl(owner: str, aces: list[Ace] | None, user: str, *, final: bool) -> None:
    """Conservative explicit allow policy; never infer that an unknown ACE is safe.

    Ancestors may allow adding children, but must not allow replacing existing
    entries or changing their own ACL/reparse metadata. Final directories/files
    additionally reject untrusted data/add-child writes. Deny ACEs are not used
    to justify otherwise unsafe grants; unusual enterprise ACLs fail closed.
    """
    trusted = TRUSTED | {user}
    if owner not in trusted or aces is None or len(aces) > 1024:
        raise ValueError("WINDOWS_CACHE_SECURITY_UNSAFE")
    dangerous = DELETE | 0x40000 | 0x80000 | 0x100 | 0x10 | 0x40
    if final:
        dangerous |= 0x2 | 0x4
    for ace in aces:
        if ace.kind not in (0, 1):
            raise ValueError("WINDOWS_CACHE_ACE_UNSUPPORTED")
        if ace.kind == 1 or ace.flags & 0x08:  # DENY, or INHERIT_ONLY (not this object).
            continue
        if ace.sid not in trusted and (ace.mask & dangerous or ace.mask & 0x50000000):
            raise ValueError("WINDOWS_CACHE_SECURITY_UNSAFE")


def unicode_argument(value: str) -> tuple[Any, UnicodeString]:
    raw = value.encode("utf-16-le", errors="strict")
    if not raw or len(raw) > 65532 or "\0" in value:
        raise ValueError("WINDOWS_CACHE_NAME_INVALID")
    buffer = (U16 * (len(raw) // 2 + 1))()
    C.memmove(buffer, raw, len(raw))
    return buffer, UnicodeString(len(raw), len(raw) + 2, C.cast(buffer, PTR))


def rename_argument(parent: int, target: str, replace: bool) -> bytes:
    # Native FILE_RENAME_INFORMATION/FILE_LINK_INFORMATION x64: BOOLEAN at 0,
    # HANDLE at 8, ULONG byte length at 16, WCHAR payload begins at 20 (not 24).
    raw = component(target).encode("utf-16-le")
    return struct.pack("<B7xQI", int(replace), parent, len(raw)) + raw


class NativeWindowsApi:
    def __init__(self) -> None:
        if os.name != "nt" or C.sizeof(PTR) != 8:
            raise ValueError("WINDOWS_CACHE_NATIVE_PLATFORM_REQUIRED")
        loader = getattr(C, "WinDLL")
        self.kernel: Any = loader("kernel32", use_last_error=True)
        self.advapi: Any = loader("advapi32", use_last_error=True)
        self.nt: Any = loader("ntdll", use_last_error=True)
        self._bind()
        self.user = self._user_sid()

    @staticmethod
    def _function(library: Any, name: str, result: Any, args: list[Any]) -> None:
        function = getattr(library, name)
        function.restype, function.argtypes = result, args

    def _bind(self) -> None:
        bind = self._function
        bind(self.nt, "NtCreateFile", I32, [PTR, U32, PTR, PTR, PTR, U32, U32, U32, U32, PTR, U32])
        bind(self.nt, "NtSetInformationFile", I32, [PTR, PTR, PTR, U32, U32])
        bind(
            self.nt,
            "NtQueryDirectoryFile",
            I32,
            [PTR, PTR, PTR, PTR, PTR, PTR, U32, U32, U8, PTR, U8],
        )
        bind(self.nt, "RtlNtStatusToDosError", U32, [I32])
        bind(self.kernel, "CloseHandle", I32, [PTR])
        bind(self.kernel, "GetFileInformationByHandleEx", I32, [PTR, I32, PTR, U32])
        bind(self.kernel, "GetFileType", U32, [PTR])
        bind(self.kernel, "FlushFileBuffers", I32, [PTR])
        bind(self.kernel, "LockFileEx", I32, [PTR, U32, U32, U32, U32, PTR])
        bind(self.kernel, "UnlockFileEx", I32, [PTR, U32, U32, U32, PTR])
        bind(self.kernel, "GetCurrentProcess", PTR, [])
        bind(self.kernel, "LocalFree", PTR, [PTR])
        bind(self.kernel, "GetDriveTypeW", U32, [C.c_wchar_p])
        bind(
            self.kernel,
            "GetVolumeInformationByHandleW",
            I32,
            [PTR, C.c_wchar_p, U32, PTR, PTR, PTR, C.c_wchar_p, U32],
        )
        bind(self.advapi, "OpenProcessToken", I32, [PTR, U32, PTR])
        bind(self.advapi, "GetTokenInformation", I32, [PTR, I32, PTR, U32, PTR])
        bind(self.advapi, "ConvertSidToStringSidW", I32, [PTR, PTR])
        bind(self.advapi, "GetSecurityInfo", U32, [PTR, I32, U32, PTR, PTR, PTR, PTR, PTR])
        bind(self.advapi, "GetAce", I32, [PTR, U32, PTR])

    @staticmethod
    def _failure(code: int) -> None:
        if code in (2, 3):
            raise FileNotFoundError(errno.ENOENT, "WINDOWS_CACHE_NOT_FOUND")
        if code in (80, 183):
            raise FileExistsError(errno.EEXIST, "WINDOWS_CACHE_EXISTS")
        if code in (32, 33):
            raise BlockingIOError(errno.EAGAIN, "WINDOWS_CACHE_BUSY")
        if code == 5:
            raise PermissionError(errno.EACCES, "WINDOWS_CACHE_ACCESS_DENIED")
        raise OSError(errno.EIO, "WINDOWS_CACHE_NATIVE_FAILURE_" + str(code))

    def _bool(self, result: Any) -> None:
        if not result:
            self._failure(int(getattr(C, "get_last_error")()))

    def _status(self, status: int) -> None:
        if status < 0:
            self._failure(int(self.nt.RtlNtStatusToDosError(status)))
        if status != 0:
            raise ValueError("WINDOWS_CACHE_NATIVE_STATUS_UNCONFIRMED")

    def _completed(self, returned: int, status: IoStatus) -> None:
        self._status(returned)
        final = I32(int(status.StatusOrPointer or 0) & 0xFFFFFFFF).value
        self._status(final)  # No success receipt from return=0 with a failed/pending IOSB.

    def close(self, handle: int) -> None:
        self._bool(self.kernel.CloseHandle(handle))

    def _sid(self, pointer: Any) -> str:
        if not pointer:
            raise ValueError("WINDOWS_CACHE_SID_MISSING")
        value = PTR()
        self._bool(self.advapi.ConvertSidToStringSidW(pointer, C.byref(value)))
        try:
            return C.wstring_at(value)
        finally:
            self.kernel.LocalFree(value)

    def _user_sid(self) -> str:
        token = PTR()
        self._bool(self.advapi.OpenProcessToken(self.kernel.GetCurrentProcess(), 8, C.byref(token)))
        try:
            length = U32()
            self.advapi.GetTokenInformation(token, 1, None, 0, C.byref(length))
            if not 0 < length.value <= 65536:
                raise ValueError("WINDOWS_CACHE_TOKEN_INVALID")
            buffer = C.create_string_buffer(length.value)
            self._bool(self.advapi.GetTokenInformation(token, 1, buffer, length, C.byref(length)))
            return self._sid(C.cast(buffer, C.POINTER(PTR))[0])
        finally:
            self.close(int(token.value or 0))

    def security(self, handle: int, *, final: bool) -> None:
        owner, dacl, descriptor = PTR(), PTR(), PTR()
        code = int(
            self.advapi.GetSecurityInfo(
                handle, 1, 5, C.byref(owner), None, C.byref(dacl), None, C.byref(descriptor)
            )
        )
        if code:
            self._failure(code)
        try:
            aces = None
            if dacl.value:
                header = C.cast(dacl, C.POINTER(AclHeader)).contents
                if header.Count > 1024 or header.Size < C.sizeof(AclHeader):
                    raise ValueError("WINDOWS_CACHE_ACL_INVALID")
                aces = []
                for index in range(header.Count):
                    pointer = PTR()
                    self._bool(self.advapi.GetAce(dacl, index, C.byref(pointer)))
                    raw_header = C.string_at(pointer, 4)
                    kind, flags, size = struct.unpack("<BBH", raw_header)
                    if kind not in (0, 1) or size < 16:
                        raise ValueError("WINDOWS_CACHE_ACE_UNSUPPORTED")
                    mask = U32.from_address(int(pointer.value or 0) + 4).value
                    aces.append(Ace(kind, flags, mask, self._sid(int(pointer.value or 0) + 8)))
            validate_acl(self._sid(owner), aces, self.user, final=final)
        finally:
            self.kernel.LocalFree(descriptor)

    def _open(
        self,
        parent: int | None,
        name: str,
        *,
        directory: bool,
        create: str = "open",
        write: bool = False,
        delete: bool = False,
    ) -> int:
        buffer, text = unicode_argument(name)
        attributes = ObjectAttributes(
            C.sizeof(ObjectAttributes), parent, C.cast(C.pointer(text), PTR), 0x40, None, None
        )
        result, status = PTR(), IoStatus()
        access = READ_CONTROL | SYNCHRONIZE | 0x80
        access |= 0x21 if directory else 1
        if write:
            access |= 0x116  # data/add-file, append/add-directory, EA and attributes.
        if delete:
            access |= DELETE
        options = (
            0x200000 | 0x20 | (1 if directory else 0x40)
        )  # OPEN_REPARSE_POINT, synchronous, kind.
        if write:
            options |= 2  # FILE_WRITE_THROUGH; does not excuse a failed flush receipt.
        value = int(
            self.nt.NtCreateFile(
                C.byref(result),
                access,
                C.byref(attributes),
                C.byref(status),
                None,
                0x80,
                3 if directory else 7,
                {"open": 1, "create": 2, "update": 3}[create],
                options,
                None,
                0,
            )
        )
        try:
            self._completed(value, status)
        except BaseException:
            if result.value:
                self.close(int(result.value))
            raise
        if not result.value:
            raise ValueError("WINDOWS_CACHE_HANDLE_MISSING")
        return int(result.value)

    def root(self, anchor: str) -> int:
        if self.kernel.GetDriveTypeW(anchor) != 3:
            raise ValueError("WINDOWS_CACHE_LOCAL_VOLUME_REQUIRED")
        handle = self._open(None, "\\??\\" + anchor, directory=True)
        try:
            serial, maximum, flags = U32(), U32(), U32()
            filesystem = C.create_unicode_buffer(32)
            self._bool(
                self.kernel.GetVolumeInformationByHandleW(
                    handle,
                    None,
                    0,
                    C.byref(serial),
                    C.byref(maximum),
                    C.byref(flags),
                    filesystem,
                    32,
                )
            )
            if filesystem.value.upper() != "NTFS" or not flags.value & 8:
                raise ValueError("WINDOWS_CACHE_NTFS_ACL_REQUIRED")
            return handle
        except BaseException:
            self.close(handle)
            raise

    def child(
        self,
        parent: int,
        name: str,
        *,
        directory: bool,
        create: str = "open",
        write: bool = False,
        delete: bool = False,
    ) -> int:
        return self._open(
            parent, component(name), directory=directory, create=create, write=write, delete=delete
        )

    def info(self, handle: int) -> Info:
        if self.kernel.GetFileType(handle) != 1:
            raise ValueError("WINDOWS_CACHE_DISK_FILE_REQUIRED")
        identity, tag, standard = FileId(), AttributeTag(), StandardInfo()
        for kind, value in ((18, identity), (9, tag), (1, standard)):
            self._bool(
                self.kernel.GetFileInformationByHandleEx(
                    handle, kind, C.byref(value), C.sizeof(value)
                )
            )
        if tag.Attributes & REPARSE or standard.DeletePending:
            raise ValueError("WINDOWS_CACHE_REPARSE_OR_DELETE_PENDING")
        return Info(
            Identity(identity.Volume, bytes(identity.Identifier)),
            tag.Attributes,
            standard.Size,
            bool(standard.Directory),
        )

    @staticmethod
    def from_fd(descriptor: int) -> int:
        import msvcrt

        return int(getattr(msvcrt, "get_osfhandle")(descriptor))

    def adopt(self, handle: int, *, readonly: bool) -> int:
        """Consumes the HANDLE on every outcome; CRT owns it after successful adoption."""
        import msvcrt

        try:
            descriptor = int(
                getattr(msvcrt, "open_osfhandle")(
                    handle, (os.O_RDONLY if readonly else os.O_RDWR) | getattr(os, "O_BINARY")
                )
            )
        except BaseException:
            self.close(handle)
            raise
        try:
            os.set_inheritable(descriptor, False)
        except BaseException:
            os.close(descriptor)  # Never CloseHandle after ownership transferred to CRT.
            raise
        return descriptor

    def flush(self, handle: int) -> None:
        self._bool(self.kernel.FlushFileBuffers(handle))

    def publish(self, source: int, parent: int, target: str, *, replace: bool) -> None:
        payload = rename_argument(parent, target, replace)
        buffer, status = C.create_string_buffer(payload), IoStatus()
        self._completed(
            int(
                self.nt.NtSetInformationFile(
                    source, C.byref(status), buffer, len(payload), 10 if replace else 11
                )
            ),
            status,
        )

    def remove(self, handle: int) -> None:
        value, status = U8(1), IoStatus()
        self._completed(
            int(self.nt.NtSetInformationFile(handle, C.byref(status), C.byref(value), 1, 13)),
            status,
        )

    def lock(self, handle: int, *, unlock: bool = False) -> None:
        overlap = Overlapped()
        if unlock:
            self._bool(self.kernel.UnlockFileEx(handle, 0, 1, 0, C.byref(overlap)))
        else:
            self._bool(self.kernel.LockFileEx(handle, 3, 0, 1, 0, C.byref(overlap)))

    def names(self, handle: int) -> list[str]:
        result: list[str] = []
        first = True
        while True:
            buffer, status = C.create_string_buffer(65536), IoStatus()
            value = int(
                self.nt.NtQueryDirectoryFile(
                    handle,
                    None,
                    None,
                    None,
                    C.byref(status),
                    buffer,
                    len(buffer),
                    12,
                    0,
                    None,
                    int(first),
                )
            )
            first = False
            if value & 0xFFFFFFFF == 0x80000006:
                if int(status.StatusOrPointer or 0) & 0xFFFFFFFF not in (0, 0x80000006):
                    self._status(I32(int(status.StatusOrPointer or 0) & 0xFFFFFFFF).value)
                return result
            self._completed(value, status)
            used = int(status.Information)
            if not 0 < used <= len(buffer):
                raise ValueError("WINDOWS_CACHE_ENUMERATION_INVALID")
            offset = 0
            raw = buffer.raw[:used]
            while True:
                if offset + 12 > used:
                    raise ValueError("WINDOWS_CACHE_ENUMERATION_INVALID")
                advance, _, length = struct.unpack_from("<III", raw, offset)
                if length % 2 or offset + 12 + length > used:
                    raise ValueError("WINDOWS_CACHE_ENUMERATION_INVALID")
                name = raw[offset + 12 : offset + 12 + length].decode("utf-16-le", errors="strict")
                if name not in (".", ".."):
                    result.append(component(name))
                if not advance:
                    break
                if advance % 4 or advance < 12 + length:
                    raise ValueError("WINDOWS_CACHE_ENUMERATION_INVALID")
                offset += advance


class WindowsDirectory:
    """Held NTFS handles; deliberately not selected by local_directory() yet."""

    def __init__(self, path: Path, *, api: NativeWindowsApi | None = None):
        self.api = api if api is not None else NativeWindowsApi()
        self.path = path
        lexical = PureWindowsPath(str(path))
        if not lexical.is_absolute() or not re.fullmatch(r"[A-Za-z]:", lexical.drive):
            raise ValueError("WINDOWS_CACHE_LOCAL_PATH_REQUIRED")
        self.anchor = lexical.anchor
        parts = [component(part) for part in lexical.parts[1:]]
        self._chain: list[tuple[str, int, Identity]] = []
        try:
            handle = self.api.root(self.anchor)
            self._keep(self.anchor, handle, not parts)
            for index, part in enumerate(parts):
                handle = self.api.child(handle, part, directory=True, write=index == len(parts) - 1)
                self._keep(part, handle, index == len(parts) - 1)
            self.verify()
        except BaseException:
            self.close()
            raise

    def _keep(self, name: str, handle: int, final: bool) -> None:
        try:
            identity = self._check(handle, True, final).identity
        except BaseException:
            self.api.close(handle)
            raise
        self._chain.append((name, handle, identity))

    @property
    def _handle(self) -> int:
        if not self._chain:
            raise ValueError("WINDOWS_CACHE_CLOSED")
        return self._chain[-1][1]

    def _check(self, handle: int, directory: bool, final: bool = True) -> Info:
        value = self.api.info(handle)
        if (
            value.attributes & REPARSE
            or value.directory != directory
            or bool(value.attributes & DIRECTORY) != directory
        ):
            raise ValueError("WINDOWS_CACHE_TYPE_INVALID")
        self.api.security(handle, final=final)
        if self._chain and value.identity.volume != self._chain[0][2].volume:
            raise ValueError("WINDOWS_CACHE_VOLUME_CHANGED")
        return value

    def verify(self) -> None:
        self._handle
        probe = self.api.root(self.anchor)
        try:
            if self._check(probe, True, len(self._chain) == 1).identity != self._chain[0][2]:
                raise ValueError("WINDOWS_CACHE_ROOT_REPLACED")
        finally:
            self.api.close(probe)
        for index, (name, held, identity) in enumerate(self._chain):
            if self._check(held, True, index == len(self._chain) - 1).identity != identity:
                raise ValueError("WINDOWS_CACHE_REPLACED")
            if index:
                probe = self.api.child(self._chain[index - 1][1], name, directory=True)
                try:
                    if self._check(probe, True, index == len(self._chain) - 1).identity != identity:
                        raise ValueError("WINDOWS_CACHE_REPLACED")
                finally:
                    self.api.close(probe)

    def child(self, name: str, *, create: bool = False) -> LocalDirectory:
        self.verify()
        name = component(name)
        handle = self.api.child(
            self._handle, name, directory=True, create="update" if create else "open", write=True
        )
        try:
            self._check(handle, True)
            if create:
                self.sync()
            result = WindowsDirectory(self.path / name, api=self.api)
            try:
                if result._chain[-1][2] != self.api.info(handle).identity:
                    raise ValueError("WINDOWS_CACHE_REPLACED")
                self.verify()
            except BaseException:
                result.close()
                raise
            return result
        finally:
            self.api.close(handle)

    def names(self) -> list[str]:
        self.verify()
        result = self.api.names(self._handle)
        self.verify()
        return result

    def open_file(self, name: str, access: Access = "read") -> int:
        self.verify()
        if access not in ("read", "update", "exclusive"):
            raise ValueError("WINDOWS_CACHE_ACCESS_INVALID")
        handle = self.api.child(
            self._handle,
            component(name),
            directory=False,
            create={"read": "open", "update": "update", "exclusive": "create"}[access],
            write=access != "read",
        )
        try:
            self._check(handle, False)
            self.verify()
        except BaseException:
            self.api.close(handle)
            raise
        # adopt consumes the HANDLE on both success and failure; only CRT may
        # close it afterwards. Callers own the returned non-inheritable fd.
        return self.api.adopt(handle, readonly=access == "read")

    def verify_file(self, name: str, descriptor: int) -> None:
        self.verify()
        held = self._check(self.api.from_fd(descriptor), False)
        handle = self.api.child(self._handle, component(name), directory=False)
        try:
            if self._check(handle, False).identity != held.identity:
                raise ValueError("WINDOWS_CACHE_FILE_REPLACED")
        finally:
            self.api.close(handle)

    def publish(self, source: str, target: str, *, replace: bool = False) -> None:
        self.verify()
        source, target = component(source), component(target)
        handle = self.api.child(self._handle, source, directory=False, write=True, delete=True)
        try:
            self._check(handle, False)
            if replace:
                try:
                    existing = self.api.child(self._handle, target, directory=False)
                except FileNotFoundError:
                    pass
                else:
                    try:
                        self._check(existing, False)
                    finally:
                        self.api.close(existing)
            self.api.flush(handle)
            self.api.publish(handle, self._handle, target, replace=replace)
            self.api.flush(handle)
            self.sync()  # Never substitute success if native directory flush is unsupported.
        finally:
            self.api.close(handle)

    def remove(self, name: str, *, missing_ok: bool = False) -> None:
        self.verify()
        try:
            handle = self.api.child(self._handle, component(name), directory=False, delete=True)
        except FileNotFoundError:
            if missing_ok:
                return
            raise
        try:
            self._check(handle, False)
            self.api.remove(handle)
        finally:
            self.api.close(handle)

    def sync(self) -> None:
        self.verify()
        self.api.flush(self._handle)  # Actual NTFS receipt is a native acceptance gate.

    def sync_file(self, descriptor: int) -> None:
        self.verify()
        handle = self.api.from_fd(descriptor)
        self._check(handle, False)
        self.api.flush(handle)

    def writer_lock(self, name: str) -> LocalWriterLock:
        return WindowsWriterLock(self, component(name))

    def owner_lock(self, name: str) -> "WindowsOwnerLock":
        return WindowsOwnerLock(self, component(name))

    def close(self) -> None:
        while self._chain:
            self.api.close(self._chain[-1][1])
            self._chain.pop()  # Failed close retains ownership instead of reporting quiescence.


class WindowsWriterLock:
    def __init__(self, directory: WindowsDirectory, name: str):
        self.directory, self.name = directory, name
        self.fd: int | None = directory.open_file(name, "update")
        try:
            directory.api.lock(directory.api.from_fd(self.fd))
            self.verify()
        except BaseException:
            os.close(self.fd)
            self.fd = None
            raise

    def verify(self) -> None:
        if self.fd is None:
            raise ValueError("WINDOWS_CACHE_LOCK_CLOSED")
        self.directory.verify_file(self.name, self.fd)

    def close(self) -> None:
        if self.fd is not None:
            # Closing the owned CRT fd releases its native byte-range lock.
            # Cleanup must not revalidate a possibly replaced namespace first.
            os.close(self.fd)
            self.fd = None
        # Never remove the permanent inode, even after process death.


class WindowsOwnerLock(WindowsWriterLock):
    """Protected equivalent of ProjectLock, including its legacy marker refusal."""

    def __init__(self, directory: WindowsDirectory, name: str):
        from uuid import uuid4
        from easyai.security.project_lock import MAGIC

        self.reason: str | None = None
        temporary = ".owner-init-" + str(uuid4())
        try:
            with os.fdopen(directory.open_file(temporary, "exclusive"), "wb") as output:
                output.write(MAGIC)
                output.flush()
                directory.sync_file(output.fileno())
            try:
                directory.publish(temporary, name)
            except FileExistsError:
                pass
        finally:
            directory.remove(temporary, missing_ok=True)
        try:
            super().__init__(directory, name)
        except BlockingIOError:
            self.directory, self.name, self.fd = directory, name, None
            self.reason = "PROJECT_LOCK_HELD"
            return
        assert self.fd is not None
        try:
            os.lseek(self.fd, 0, os.SEEK_SET)
            if os.read(self.fd, len(MAGIC) + 1) != MAGIC:
                self.reason = "PROJECT_LOCK_LEGACY_UNVERIFIED"
                self.close()
        except BaseException:
            self.close()
            raise
