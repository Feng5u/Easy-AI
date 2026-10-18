from pathlib import PurePosixPath, PureWindowsPath


def artifact_relative_path(value: str) -> str:
    """Validate output intent for both client/target path dialects, without I/O."""
    windows = PureWindowsPath(value)
    posix = PurePosixPath(value)
    if (
        not value
        or len(value) > 256
        or windows.drive
        or windows.root
        or posix.is_absolute()
        or "\\" in value
        or ".." in posix.parts
        or any(ord(c) < 32 for c in value)
        or any(c in value for c in ':*?"<>|')
    ):
        raise ValueError("OUTPUT_PATH_FORBIDDEN")
    if posix.suffix.lower() != ".png":
        raise ValueError("OUTPUT_PATH_FORBIDDEN")
    canonical = (
        posix if posix.parts[0] == "outputs" else PurePosixPath("outputs") / posix
    ).as_posix()
    if len(canonical) > 256:
        raise ValueError("OUTPUT_PATH_FORBIDDEN")
    # Reserve the complete physical suffix through the maximum supported epoch:
    # __<16 ASCII hash>__epoch-10000. Never truncate a user's logical name.
    if any(len(part.encode("utf-8")) > 255 for part in posix.parts) or (
        len(posix.stem.encode("utf-8")) + 31 + len(posix.suffix.encode("utf-8")) > 255
    ):
        raise ValueError("OUTPUT_PATH_FORBIDDEN")
    return canonical
