"""Metadata and controlled command contracts; no wheel download, install or ML import."""

import hashlib
import ast
import json
import threading

import pytest
from packaging.markers import default_environment
from packaging.requirements import Requirement
from packaging.specifiers import SpecifierSet
from packaging.utils import canonicalize_name, parse_wheel_filename

from easyai.domain.install import InstallPlanRequest
from easyai.services.install_process import OfflineWheelInstaller
from easyai.services.install_process import ManagedInstallInspector
from easyai.services.install_runtime import InstallRuntime
from easyai.services.install_service import InstallService, PROFILE_ROOT, digest
from easyai.services.install_service import ProbeReceipt
from easyai.services.install_sources import (
    ML_HEADER,
    ML_ROOTS,
    constraints_hash,
    lock_bytes,
    wheels,
)
from test_install_runtime import configured as configured_fixture
from test_install_process import owned as owned_fixture
from test_install_service import ControlledExecutor

configured = configured_fixture
owned = owned_fixture


def test_pinned_wheel_metadata_closure_matches_cpu_core():
    data = json.loads((PROFILE_ROOT / "easyai-ml-sources.json").read_bytes())
    selected = wheels(PROFILE_ROOT, set(ML_ROOTS))
    versions = {w["name"]: w["version"] for w in selected}
    environment = default_environment()
    environment.update(
        python_version="3.11",
        python_full_version="3.11.17",
        sys_platform="linux",
        platform_machine="x86_64",
        extra="",
    )
    for package in data["packages"]:
        assert SpecifierSet(package["requiresPython"]).contains("3.11.17")
        assert package["yanked"] is False and package["knownVulnerabilitiesAtCapture"] == []
        name, version, _, tags = parse_wheel_filename(package["filename"])
        assert name == canonicalize_name(package["name"]) and str(version) == package["version"]
        assert any(
            t.platform == "any" or (t.interpreter == "cp311" and t.platform.endswith("x86_64"))
            for t in tags
        )
        assert package["url"].startswith("https://files.pythonhosted.org/")
        assert package["metadataUrl"] == package["url"] + ".metadata"
        assert len(package["sha256"]) == len(package["metadataSha256"]) == 64
        active = []
        for raw in package["requiresDist"]:
            dependency = Requirement(raw)
            if dependency.marker is not None and not dependency.marker.evaluate(environment):
                continue
            key = canonicalize_name(dependency.name)
            assert not dependency.extras and not dependency.url
            assert key in versions and dependency.specifier.contains(versions[key])
            active.append(key)
        assert set(active) == set(data["dependencies"][package["name"]])
    assert {"numpy", "python-dateutil"} <= versions.keys()  # Reuse exact core pins.


def test_single_and_full_ml_plans_use_only_their_reviewed_closure(tmp_path):
    service = InstallService(tmp_path)
    try:

        def plan(ids):
            return service.plan(
                InstallPlanRequest(
                    target_id="local",
                    profile_id="easyai-cpu",
                    package_ids=ids,
                    new_environment_spec={"name": "ml"},
                )
            )

        core_names = {w["name"] for w in wheels(PROFILE_ROOT)}
        for ids, additions in [
            (["scipy"], {"scipy"}),
            (["pandas"], {"pandas"}),
            (["scikit-learn"], {"scipy", "scikit-learn", "joblib", "threadpoolctl"}),
            (
                ["numpy", "scipy", "pandas", "matplotlib", "scikit-learn"],
                {"scipy", "pandas", "scikit-learn", "joblib", "threadpoolctl"},
            ),
        ]:
            value = plan(ids)
            assert not value.blockers and not value.execution_enabled
            assert {c.package_id for c in value.package_changes} == core_names | additions
            assert {c.package_id for c in value.package_changes if c.requested} == set(ids)
            assert value.download_bytes == sum(
                w["downloadBytes"] for w in wheels(PROFILE_ROOT, set(ids))
            )
            assert value.installed_bytes is None  # No invented extraction size.
            assert value.plan_hash == digest(value.model_dump(exclude={"plan_hash"}))
        blocked = plan(["scipy", "spacy"])
        assert "INSTALL_DEPENDENCIES_UNRESOLVED" in blocked.blockers
        assert blocked.download_bytes is blocked.installed_bytes is None
        assert not blocked.execution_enabled
        catalog = {c.package_id: c for c in service.catalog().packages}
        assert catalog["scikit-learn"].import_name == "sklearn"
        assert len([c for c in catalog.values() if c.target_version]) == 10
    finally:
        service.close()


def test_fixed_installer_consumes_selected_ml_lock_and_rejects_drift(tmp_path):
    service = InstallService(tmp_path)
    plan = service.plan(
        InstallPlanRequest(
            target_id="local",
            profile_id="easyai-cpu",
            package_ids=["scikit-learn"],
            new_environment_spec={"name": "ml"},
        )
    )
    prefix = service.root / plan.environment_id
    (prefix / "bin").mkdir(parents=True)
    (prefix / "bin/python").write_text("never execute")
    (prefix / ".easyai-owned.json").write_text(
        json.dumps({"ownedByEasyAI": True, "environmentId": plan.environment_id})
    )
    command_root = tmp_path / "commands"
    command_root.mkdir()
    calls = []

    class Commands:
        root = command_root

        def run(self, argv, cwd, cancel, progress):
            compile(argv[-1], "<fixed-pip-only>", "exec")
            calls.append(argv)
            return "completed", []

    installer = OfflineWheelInstaller(Commands(), tmp_path, authorized=True)
    try:
        assert installer.install(prefix, plan, threading.Event(), lambda: None) == "completed"
        contents = next(command_root.glob("*.lock")).read_bytes()
        assert contents == lock_bytes(PROFILE_ROOT, {"scikit-learn"})
        assert b"joblib==" in contents and b"pandas==" not in contents
        assert "--no-index" in calls[0][-1] and "--require-hashes" in calls[0][-1]
        plan.constraints_hash = "f" * 64
        with pytest.raises(ValueError, match="INSTALL_PLAN_STALE"):
            installer.install(prefix, plan, threading.Event(), lambda: None)
        assert len(calls) == 1
    finally:
        service.close()


def test_ml_runtime_binds_selected_sources_and_budget(configured):
    app, sources, config = configured
    profiles = sources / "profile"
    path = sources / "wheels/scipy-fixture.whl"
    path.write_bytes(b"synthetic inventory, never a wheel or installed")
    item = {
        "name": "scipy",
        "version": "fixture",
        "filename": path.name,
        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "downloadBytes": path.stat().st_size,
    }
    (profiles / "easyai-ml-sources.json").write_text(
        json.dumps({"packages": [item], "dependencies": {"scipy": []}})
    )
    (profiles / "easyai-ml-linux-cp311.lock").write_text(
        ML_HEADER + f"scipy==fixture \\\n    --hash=sha256:{item['sha256']}\n"
    )
    runtime = InstallRuntime(app)
    core = runtime.snapshot()
    selected = runtime.snapshot({"scipy"})
    assert core.enabled and selected.enabled and core.fingerprint != selected.fingerprint
    path.write_bytes(b"changed")
    with pytest.raises(ValueError):
        runtime.snapshot({"scipy"})
    assert (
        runtime.snapshot().fingerprint == core.fingerprint
    )  # Missing optional does not break core.
    path.write_bytes(b"synthetic inventory, never a wheel or installed")
    core_size = (
        sum(a["bytes"] for a in config["bootstrap"])
        + (sources / "wheels/torch-fixture.whl").stat().st_size
    )
    config["diskBudgetBytes"] = core_size
    (app / "install-runtime.json").write_text(json.dumps(config))
    assert runtime.snapshot().enabled
    with pytest.raises(ValueError, match="INSTALL_DISK_BUDGET_EXCEEDED"):
        runtime.snapshot({"scipy"})


def test_ml_sources_and_lock_drift_change_constraints(tmp_path):
    for path in PROFILE_ROOT.iterdir():
        if path.suffix in {".json", ".lock"}:
            (tmp_path / path.name).write_bytes(path.read_bytes())
    before = constraints_hash(tmp_path)
    path = tmp_path / "easyai-ml-sources.json"
    data = json.loads(path.read_bytes())
    data["packages"][0]["downloadBytes"] += 1
    path.write_text(json.dumps(data))
    assert constraints_hash(tmp_path) != before
    path = tmp_path / "easyai-ml-linux-cp311.lock"
    path.write_bytes(path.read_bytes() + b"unreviewed==1\n")
    with pytest.raises(ValueError, match="INSTALL_DEPENDENCIES_UNRESOLVED"):
        wheels(tmp_path, {"scipy"})


def test_selected_ml_import_failure_never_verifies_or_keeps_lease(owned):
    service, _, _, prefix, inventory, request = owned
    # The fixture's original torch job has not executed; cancel before the new plan.
    original = next(iter(service._jobs.values()))
    service.cancel(original.job_id)
    data = request.model_dump()
    data["package_ids"] = ["scikit-learn"]
    plan = service.plan(InstallPlanRequest(**data))
    from test_install_service import confirmation

    job = service.confirm(confirmation(plan))

    class Installer(ControlledExecutor):
        def install(self, *args):
            inventory.write_text(
                json.dumps(
                    {
                        "versions": {c.package_id: c.target_version for c in plan.package_changes},
                        "imports": {
                            "torch": True,
                            "torchvision": True,
                            "matplotlib": True,
                            "scipy": True,
                            "sklearn": False,
                            "joblib": True,
                            "threadpoolctl": True,
                        },
                        "tensor_ok": True,
                    }
                )
            )
            return "completed"

    result = service.execute(job.job_id, Installer())
    assert result.state == "FAILED" and not result.verified and result.needs_reprobe
    assert job.job_id not in service._leases and not (prefix / ".easyai-ready.json").exists()


def test_fixed_probe_imports_only_explicit_modules(tmp_path, monkeypatch):
    prefix = tmp_path / "prefix"
    (prefix / "bin").mkdir(parents=True)
    (prefix / "bin/python").write_text("nonexecuted")
    monkeypatch.setattr(
        "subprocess.Popen", lambda *a, **k: pytest.fail("Never run a real ML probe")
    )

    class Captured(Exception):
        pass

    class Commands:
        def run(self, argv, *args, **kwargs):
            code = ast.parse(argv[-1])
            # metadata inventory is independent of actual imports.
            imports_loop = [node for node in code.body if isinstance(node, ast.For)][1]
            seen.append(ast.literal_eval(imports_loop.iter))
            raise Captured

    seen = []
    inspector = ManagedInstallInspector(Commands())
    with pytest.raises(Captured):
        inspector.inspect_owned(prefix, "nonce", ProbeReceipt())
    assert seen[-1] == ("torch", "torchvision", "matplotlib")
    with pytest.raises(Captured):
        inspector.inspect_owned(
            prefix, "nonce", ProbeReceipt(import_names=("torch", "scipy", "sklearn"))
        )
    assert seen[-1] == ("torch", "scipy", "sklearn") and "pandas" not in seen[-1]
    with pytest.raises(ValueError, match="INSTALL_INSPECTION_INVALID"):
        inspector.inspect_owned(prefix, "nonce", ProbeReceipt(import_names=("arbitrary_module",)))
    assert len(seen) == 2
