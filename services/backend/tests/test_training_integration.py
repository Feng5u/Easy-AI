"""Explicit opt-in CPU integration; synthetic IDX proves execution, never MNIST quality."""

import json
import math
import os
import struct
import subprocess
import time
from pathlib import Path

import pytest

from easyai.compiler.pipeline import compile_project
from easyai.domain.catalog import SOURCE_ROOT
from easyai.domain.contracts import ProjectDocument
from easyai.services.project_service import ProjectService
from easyai.services.run_service import RunService, TERMINAL

TRAINING = os.environ.get("EASYAI_TRAINING_PYTHON")
ROOT = os.environ.get("EASYAI_TRAINING_TEST_ROOT")
pytestmark = pytest.mark.skipif(
    not TRAINING or not ROOT,
    reason="Explicit authorized CPU interpreter and new test root required",
)


def test_real_generated_cpu_bundle_synthetic_idx():
    assert TRAINING and ROOT
    root = Path(ROOT)
    assert root.is_absolute()
    root.mkdir(exist_ok=False)
    data = root / "合成 数据"
    raw = data / "MNIST/raw"
    raw.mkdir(parents=True)
    for name, count in (("train", 32), ("t10k", 16)):
        pixels = bytes(
            (sample * 17 + pixel * 7) % 256 for sample in range(count) for pixel in range(28 * 28)
        )
        (raw / f"{name}-images-idx3-ubyte").write_bytes(
            struct.pack(">IIII", 2051, count, 28, 28) + pixels
        )
        (raw / f"{name}-labels-idx1-ubyte").write_bytes(
            struct.pack(">II", 2049, count) + bytes(sample % 10 for sample in range(count))
        )
    project_root = root / "项目 snapshot"
    project_root.mkdir()
    value = json.loads(
        (SOURCE_ROOT / "packages/contracts/fixtures/mnist-figures.json").read_bytes()
    )
    from test_lowering import nodes

    for node in nodes(value):
        if node["type"] == "train.loop":
            node["fields"]["EPOCHS"] = 1
        if node["type"] == "data.dataloader":
            node["fields"]["BATCH_SIZE"] = 8
    document = ProjectDocument.model_validate(value)
    (project_root / "project.easyai.json").write_text(document.model_dump_json(by_alias=True))
    run_root = root / "runs"
    run_root.mkdir()
    project = ProjectService(project_root)
    service = RunService(run_root)
    started = time.monotonic()
    try:
        run = service.prepare(
            project,
            document.revision,
            compile_project(document).result.program_hash,
            "explicit-synthetic-idx-only",
            Path(TRAINING),
            data,
        )
        run = service.start(run.run_id)
        while run.status not in TERMINAL:
            assert time.monotonic() - started < 1800, "30 minute integration budget"
            budget_root = Path(TRAINING).parent.parent.parent
            size = sum(
                p.stat().st_size
                for p in budget_root.rglob("*")
                if p.is_file() and not p.is_symlink()
            )
            assert size <= 5_000_000_000, "5 GB owned training disk budget"
            time.sleep(0.02)
            run = service.get(run.run_id)
        directory = Path(run.config.run_root)
        events = service.events(run.run_id)
        assert run.status == "SUCCEEDED", (
            run.status,
            [e.model_dump() for e in events if e.type == "runtime_error"],
            (directory / "logs/stderr.log").read_text(),
        )
        assert len([e for e in events if e.type == "process_exited"]) == 1
        assert next(e for e in events if e.type == "process_exited").payload["exitCode"] == 0
        metrics = next(e.payload for e in events if e.type == "epoch_completed")
        assert metrics["train_samples"] == 32 and metrics["test_samples"] == 16
        assert math.isfinite(metrics["train_loss"]) and 0 <= metrics["test_accuracy"] <= 1
        assert (directory / "metrics/epochs.csv").read_text().count("\n") == 2
        figures = list((directory / "outputs").rglob("*.png"))
        assert len(figures) == 3 and all(
            path.read_bytes().startswith(b"\x89PNG\r\n\x1a\n") for path in figures
        )
        assert (directory / "outputs/model.pth").stat().st_size > 0
        # Recreate seed-identical initial parameters in the selected training
        # interpreter; loading the generated module does not run its main guard.
        verifier = """
import json,runpy,sys,torch
from pathlib import Path
from PIL import Image
root=Path(sys.argv[1]);sys.path.insert(0,str(root/'code'))
module=runpy.run_path(str(root/'code/train.py'),run_name='__validation__')
config=json.loads((root/'run-config.json').read_text())
program=json.loads((root/'program.ir.json').read_text())
torch.manual_seed(config['seed']);initial=module[program['model']['name']]().state_dict()
trained=torch.load(root/'outputs/model.pth',map_location='cpu',weights_only=True)
changed=[name for name in initial if not torch.equal(initial[name],trained[name])]
assert changed and set(initial)==set(trained)
for path in (root/'outputs').rglob('*.png'):
 with Image.open(path) as image:image.verify()
print(json.dumps({'changedParameterTensors':len(changed),'totalParameterTensors':len(initial),'actualPngDecode':True}))
"""
        verified = subprocess.run(
            [TRAINING, "-B", "-c", verifier, str(directory)],
            env={
                **os.environ,
                "MPLCONFIGDIR": str(directory / "cache/matplotlib"),
                "XDG_CACHE_HOME": str(directory / "cache"),
                "OMP_NUM_THREADS": "1",
            },
            capture_output=True,
            text=True,
            timeout=120,
        )
        assert verified.returncode == 0, verified.stderr
        report = {
            "scope": "synthetic IDX execution only, not MNIST learning quality",
            "runId": run.run_id,
            "status": run.status,
            "programHash": run.config.program_hash,
            "codeHash": run.config.code_hash,
            "bundleHash": run.config.bundle_hash,
            "metrics": metrics,
            "figures": len(figures),
            "parameterCheck": json.loads(verified.stdout),
            "elapsedSeconds": time.monotonic() - started,
        }
        (root / "acceptance.json").write_text(json.dumps(report, indent=2) + "\n")
        print(json.dumps(report))
    finally:
        service.close()
        project.close()
