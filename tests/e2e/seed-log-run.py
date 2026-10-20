"""Create an unstarted protocol fixture. Never probe data or start training."""

import binascii
import hashlib
import json
import struct
import sys
import zlib
from pathlib import Path

from easyai.compiler.pipeline import compile_project
from easyai.domain.contracts import ArtifactRecord
from easyai.services.local_workspace import LocalWorkspace


def png(rgb: bytes) -> bytes:
    """One synthetic color pixel, unrelated to any dataset/model/metric."""

    def chunk(kind: bytes, data: bytes) -> bytes:
        return (
            struct.pack(">I", len(data))
            + kind
            + data
            + struct.pack(">I", binascii.crc32(kind + data) & 0xFFFFFFFF)
        )

    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0))
        + chunk(b"IDAT", zlib.compress(b"\x00" + rgb))
        + chunk(b"IEND", b"")
    )


root = Path(sys.argv[1]).resolve(strict=True)
project_root = root / "project"
project_root.mkdir()
workspace = LocalWorkspace(root / "application-state" / "local-state")
try:
    session = workspace.create(
        workspace.select("project", project_root).selection_id,
        "日志协议测试夹具（未启动训练）",
    )
    document = session.project
    assert document is not None
    compiled = compile_project(document)
    run = workspace.runs.prepare(
        workspace._projects[document.project_id],
        document.revision,
        compiled.result.program_hash,
        "browser-log-fixture",
        Path(sys.executable),
        project_root / "data",
    )
    assert run.status == "CREATED"
    assert workspace.runs._supervisors == {}
    assert compiled.program is not None
    figures = [compiled.program.training.before[0], compiled.program.training.body[0]]
    output = Path(run.config.run_root) / "outputs"
    output.mkdir()
    for index, figure in enumerate(figures):
        name = f"fixture-image-{index}"
        content = png(bytes((200, 60, 60) if index == 0 else (30, 80, 210)))
        (output / f"{name}.png").write_bytes(content)
        record = ArtifactRecord(
            artifact_id=name,
            run_id=run.run_id,
            kind="figure",
            relative_path=f"outputs/{name}.png",
            mime_type="image/png",
            size_bytes=len(content),
            sha256=hashlib.sha256(content).hexdigest(),
            producer_block_id=figure.id,
            contributor_block_ids=[],
            phase="before" if index == 0 else "epoch_end",
            epoch=None if index == 0 else 1,
            sync_state="ready",
        )
        workspace.runs._journal(run.run_id).append(
            "artifact_created", figure.id, record.model_dump(by_alias=True)
        )
    workspace.runs._write_views(run.run_id, workspace.runs.events(run.run_id))
    print(json.dumps({"runId": run.run_id, "runRoot": run.config.run_root}))
finally:
    workspace.close()
