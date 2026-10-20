"""Create an unstarted protocol fixture. Never probe data or start training."""

import json
import sys
from pathlib import Path

from easyai.compiler.pipeline import compile_project
from easyai.services.local_workspace import LocalWorkspace


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
    print(json.dumps({"runId": run.run_id, "runRoot": run.config.run_root}))
finally:
    workspace.close()
