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
    return canonical
