"""Read-only archive audit against the builder's sealed unpacked inventory.

No extraction, installation, training, or network. Windows modes describe the
readonly bit, not POSIX execute permissions. Linux keeps exact POSIX modes.
"""

import hashlib
import json
import re
import stat
import sys
import tarfile
import zipfile
from pathlib import Path, PurePosixPath


def member_path(name: str) -> str:
    if not name or "\\" in name or ":" in name or "\x00" in name:
        raise ValueError("ARCHIVE_PATH_INVALID")
    path = PurePosixPath(name)
    if path.is_absolute() or any(p in {"", ".", ".."} for p in name.rstrip("/").split("/")):
        raise ValueError("ARCHIVE_PATH_INVALID")
    if any(p.endswith((".", " ")) for p in path.parts):
        raise ValueError("ARCHIVE_PATH_ALIAS")
    reserved = {
        "con",
        "prn",
        "aux",
        "nul",
        *(f"com{i}" for i in range(1, 10)),
        *(f"lpt{i}" for i in range(1, 10)),
    }
    if any(p.split(".")[0].casefold() in reserved for p in path.parts):
        raise ValueError("ARCHIVE_RESERVED_PATH")
    return path.as_posix().rstrip("/")


def audit(output: Path) -> dict:
    manifest = json.loads((output / "builder-manifest.json").read_text(encoding="utf8"))
    if (
        manifest.get("schemaVersion") != 2
        or manifest.get("distributionReady") is not False
        or manifest.get("legalReviewComplete") is not False
    ):
        raise ValueError("CANDIDATE_MANIFEST_INVALID")
    platform = manifest["platform"]
    if platform not in {"linux", "win32"} or manifest["arch"] != "x64":
        raise ValueError("CANDIDATE_PLATFORM_INVALID")
    unpacked = "win-unpacked" if platform == "win32" else "linux-unpacked"
    extension = ".zip" if platform == "win32" else ".tar.gz"
    expected = {
        r["path"][len(unpacked) + 1 :]: r
        for r in manifest["records"]
        if r["path"].startswith(unpacked + "/")
    }
    archives = [r for r in manifest["records"] if r["path"].endswith(extension)]
    if not expected or len(archives) != 1:
        raise ValueError("CANDIDATE_ARCHIVE_MISSING")
    archive = archives[0]
    archive_path = output / "artifacts" / archive["path"]
    with archive_path.open("rb") as f:
        if hashlib.file_digest(f, "sha256").hexdigest() != archive["sha256"]:
            raise ValueError("CANDIDATE_ARCHIVE_CHANGED")
    seen: set[str] = set()
    aliases: set[str] = set()
    directories = {str(PurePosixPath(name).parent) for name in expected}
    for name in list(directories):
        directories.update(str(p) for p in PurePosixPath(name).parents)

    def check(name: str, size: int, body, mode: int, readonly: bool | None = None) -> None:
        if name in seen or name not in expected:
            raise ValueError("ARCHIVE_SET_MISMATCH")
        seen.add(name)
        record = expected[name]
        if (
            size != record["bytes"]
            or hashlib.file_digest(body, "sha256").hexdigest() != record["sha256"]
        ):
            raise ValueError("ARCHIVE_BYTES_MISMATCH")
        if readonly is None:
            if mode != record["mode"]:
                raise ValueError("ARCHIVE_MODE_MISMATCH")
        elif readonly != (record["mode"] & stat.S_IWRITE == 0):
            raise ValueError("ARCHIVE_READONLY_MISMATCH")

    if platform == "win32":
        with zipfile.ZipFile(archive_path) as z:
            for item in z.infolist():
                name = member_path(item.filename)
                alias = name.casefold()
                if alias in aliases or item.flag_bits & 1:
                    raise ValueError("ARCHIVE_ALIAS_OR_ENCRYPTED")
                aliases.add(alias)
                kind = stat.S_IFMT(item.external_attr >> 16)
                if kind not in {0, stat.S_IFDIR, stat.S_IFREG}:
                    raise ValueError("ARCHIVE_LINK_OR_SPECIAL")
                if item.is_dir():
                    if item.file_size or kind not in {0, stat.S_IFDIR}:
                        raise ValueError("ARCHIVE_FILE_TYPE_MISMATCH")
                    if name not in directories:
                        raise ValueError("ARCHIVE_EXTRA_DIRECTORY")
                    continue
                if item.external_attr & 0x10 or kind == stat.S_IFDIR:
                    raise ValueError("ARCHIVE_FILE_TYPE_MISMATCH")
                with z.open(item) as body:
                    check(name, item.file_size, body, 0, bool(item.external_attr & 1))
    else:
        with tarfile.open(archive_path) as t:
            for item in t:
                path = member_path(item.name)
                parts = PurePosixPath(path).parts
                if parts[0] != "easyai-0.0.0-linux-x64":
                    raise ValueError("ARCHIVE_ROOT_MISMATCH")
                name = "/".join(parts[1:])
                if path in aliases:
                    raise ValueError("ARCHIVE_DUPLICATE")
                aliases.add(path)
                if item.isdir():
                    if item.size:
                        raise ValueError("ARCHIVE_FILE_TYPE_MISMATCH")
                    if name and name not in directories:
                        raise ValueError("ARCHIVE_EXTRA_DIRECTORY")
                    continue
                if not item.isfile():
                    raise ValueError("ARCHIVE_LINK_OR_SPECIAL")
                with t.extractfile(item) as body:
                    check(name, item.size, body, item.mode)
    if seen != expected.keys():
        raise ValueError("ARCHIVE_SET_MISMATCH")

    # Limited known-token/private-key features. Never print candidate contents;
    # this does not unpack embedded PYZ/native data or detect arbitrary secrets.
    features = [
        rb"-----BEGIN (?:RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----\s+[A-Za-z0-9+/=\r\n]{64,}",
        rb"\b(?:gh[pousr]_[A-Za-z0-9]{36,}|github_pat_[A-Za-z0-9_]{50,})\b",
        rb"\b(?:AKIA|ASIA)[A-Z0-9]{16}\b",
        rb"\bsk-(?:proj-)?[A-Za-z0-9_-]{48,}\b",
    ]
    for name in expected:
        parts = PurePosixPath(member_path(name)).parts
        if any(
            p.casefold()
            in {".git", ".ssh", ".aws", "node_modules", "runs", "data", "machine.local.json"}
            or p.casefold().startswith(".env")
            for p in parts
        ):
            raise ValueError("CANDIDATE_PRIVATE_PATH")
        body = (output / "artifacts" / unpacked / name).read_bytes()
        if any(re.search(pattern, body) for pattern in features):
            raise ValueError("CANDIDATE_SECRET_FEATURE")
    return {
        "sourceCommit": manifest["sourceCommit"],
        "platform": platform,
        "archive": archive,
        "regularFiles": len(seen),
        "bytesHashesAndSet": "PASS",
        "modePolicy": "Windows readonly only" if platform == "win32" else "exact POSIX",
        "limitedSecretFeatureScan": "PASS (raw files; no arbitrary-secret/PYZ/native assurance)",
        "distributionReady": False,
        "legalReviewComplete": False,
    }


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("Usage: verify-candidate-archive.py <builder-output>")
    output = Path(sys.argv[1]).resolve()
    result = audit(output)
    with (output / "candidate-audit.json").open("x", encoding="utf8") as f:
        json.dump(result, f, indent=2)
        f.write("\n")
    print(json.dumps(result, indent=2))
