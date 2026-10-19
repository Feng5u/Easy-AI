"""Read-only module-presence gate for our frozen sidecar, never execute its code."""

from pathlib import Path
import sys

from PyInstaller.archive.readers import CArchiveReader

if len(sys.argv) != 2 or not Path(sys.argv[1]).is_file():
    raise SystemExit("FROZEN_TRUST_EXECUTABLE_REQUIRED")
archive = CArchiveReader(sys.argv[1])
embedded = [name for name, entry in archive.toc.items() if entry[-1] == "z"]
if len(embedded) != 1:
    raise SystemExit("FROZEN_TRUST_ARCHIVE_INVALID")
modules = archive.open_embedded_archive(embedded[0]).toc
for name in (
    "easyai.security.host_keys",
    "easyai.security.windows_host_keys",
    "easyai.security.windows_store",
    "easyai.security.remote_cache",
):
    if name not in modules:
        raise SystemExit("FROZEN_TRUST_MODULE_MISSING")
print("PASS frozen host trust and native cache modules present")
