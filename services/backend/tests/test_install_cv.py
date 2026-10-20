"""CV source contracts and synthetic captures; no wheel, package import or install."""

import ast
import hashlib
import json
import threading

import pytest
from packaging.markers import default_environment
from packaging.requirements import Requirement
from packaging.specifiers import SpecifierSet

from easyai.domain.install import InstallPlanRequest
from easyai.services.install_process import ManagedInstallInspector, OfflineWheelInstaller
from easyai.services.install_runtime import InstallRuntime
from easyai.services.install_service import PROFILE_ROOT, InstallService, ProbeReceipt
from easyai.services.install_sources import (
    CV_HEADER,
    IMPORTS,
    ML_HEADER,
    constraints_hash,
    lock_bytes,
    wheels,
)
from test_install_runtime import configured as configured_fixture
from test_install_service import confirmation

configured = configured_fixture


def request(ids):
    return InstallPlanRequest(
        target_id="local",
        profile_id="easyai-cpu",
        package_ids=ids,
        new_environment_spec={"name": "cv"},
    )


def test_cv_metadata_closure_reuses_exact_core_and_scipy_pins():
    data = json.loads((PROFILE_ROOT / "easyai-cv-sources.json").read_bytes())
    selected = wheels(PROFILE_ROOT, {"scikit-image"})
    versions = {w["name"]: w["version"] for w in selected}
    env = default_environment()
    env.update(
        python_version="3.11",
        python_full_version="3.11.17",
        sys_platform="linux",
        platform_machine="x86_64",
        extra="",
    )
    for package in data["packages"]:
        assert SpecifierSet(package["requiresPython"]).contains("3.11.17")
        active = []
        for raw in package["requiresDist"]:
            dependency = Requirement(raw)
            if dependency.marker is not None and not dependency.marker.evaluate(env):
                continue
            assert not dependency.url and not dependency.extras
            assert dependency.name in versions and dependency.specifier.contains(
                versions[dependency.name]
            )
            active.append(dependency.name)
        assert set(active) == set(data["dependencies"][package["name"]])
        assert package["unpackedBytes"] is None and package["downloadBytes"] > 0
        assert package["metadataUrl"] == package["url"] + ".metadata"
        assert len(package["sha256"]) == len(package["metadataSha256"]) == 64
        assert not package["yanked"] and not package["knownVulnerabilitiesAtCapture"]
    assert {"numpy": "2.4.2", "scipy": "1.17.1", "pillow": "13.0.0"}.items() <= versions.items()
    assert (
        not {"pandas", "scikit-learn", "opencv-python", "opencv-python-headless"} & versions.keys()
    )
    candidate = data["unsupportedPackages"][0]
    assert candidate["name"] == "opencv-python" and IMPORTS["opencv-python"] == "cv2"
    # Compatible Python-level numpy constraints do not prove system library readiness.
    assert all(
        Requirement(raw).specifier.contains(versions["numpy"])
        for raw in candidate["requiresDist"]
        if Requirement(raw).marker is None or Requirement(raw).marker.evaluate(env)
    )
    assert candidate["blocker"] == "INSTALL_NATIVE_REQUIREMENTS_UNVERIFIED"


def test_cv_single_and_mixed_plans_block_opencv_without_headless(tmp_path):
    service = InstallService(tmp_path)
    try:
        value = service.plan(request(["scikit-image"]))
        selected = wheels(PROFILE_ROOT, {"scikit-image"})
        assert not value.blockers and not value.execution_enabled
        assert value.download_bytes == sum(w["downloadBytes"] for w in selected)
        assert value.installed_bytes is None
        assert {c.package_id for c in value.package_changes} == {w["name"] for w in selected}
        mixed = service.plan(request(["pandas", "scikit-image"]))
        assert not mixed.blockers
        assert len({c.package_id for c in mixed.package_changes}) == len(mixed.package_changes)
        assert "pandas" in {c.package_id for c in mixed.package_changes}
        for ids in [["opencv-python"], ["pillow", "opencv-python", "scikit-image"]]:
            blocked = service.plan(request(ids))
            assert "INSTALL_NATIVE_REQUIREMENTS_UNVERIFIED" in blocked.blockers
            assert "INSTALL_DEPENDENCIES_UNRESOLVED" in blocked.blockers
            assert (
                not blocked.execution_enabled
                and blocked.download_bytes is blocked.installed_bytes is None
            )
            assert all(c.package_id != "opencv-python-headless" for c in blocked.package_changes)
            with pytest.raises(ValueError, match="INSTALL_PLAN_BLOCKED"):
                service.confirm(confirmation(blocked))
        catalog = {c.package_id: c for c in service.catalog().packages}
        assert catalog["scikit-image"].import_name == "skimage"
        assert catalog["scikit-image"].target_version == "0.26.0"
        assert catalog["opencv-python"].target_version is None
    finally:
        service.close()


def test_cv_fixed_lock_and_probe_use_explicit_names_only(tmp_path, monkeypatch):
    monkeypatch.setattr("subprocess.Popen", lambda *a, **k: pytest.fail("No CV execution"))
    service = InstallService(tmp_path)
    plan = service.plan(request(["scikit-image"]))
    prefix = service.root / plan.environment_id
    (prefix / "bin").mkdir(parents=True)
    (prefix / "bin/python").write_text("nonexecuted")
    (prefix / ".easyai-owned.json").write_text(
        json.dumps({"ownedByEasyAI": True, "environmentId": plan.environment_id})
    )
    command_root = tmp_path / "commands"
    command_root.mkdir()
    calls = []

    class Commands:
        root = command_root

        def run(self, argv, *args, **kwargs):
            compile(argv[-1], "<captured-cv-command>", "exec")
            calls.append(argv[-1])
            return "completed", []

    try:
        assert (
            OfflineWheelInstaller(Commands(), tmp_path, authorized=True).install(
                prefix, plan, threading.Event(), lambda: None
            )
            == "completed"
        )
        lock = next(command_root.glob("*.lock")).read_bytes()
        assert lock == lock_bytes(PROFILE_ROOT, {"scikit-image"})
        assert b"scipy==1.17.1" in lock and b"scikit-image==0.26.0" in lock
        assert b"opencv" not in lock and b"pandas" not in lock
        inspector = ManagedInstallInspector(Commands())
        imports = tuple(
            module
            for name, module in IMPORTS.items()
            if name in {c.package_id for c in plan.package_changes}
        )
        with pytest.raises(ValueError, match="INSTALL_INSPECTION_FAILED"):
            inspector.inspect_owned(prefix, "nonce", ProbeReceipt(import_names=imports))
        code = ast.parse(calls[-1])
        observed = ast.literal_eval([n for n in code.body if isinstance(n, ast.For)][1].iter)
        assert "skimage" in observed and "cv2" not in observed
        assert "lazy_loader" in observed and "scikit-image" not in observed
        assert "--no-index" in calls[0] and "--require-hashes" in calls[0]
    finally:
        service.close()


def test_cv_selected_local_sources_and_budget_are_bound(configured):
    app, sources, config = configured
    profiles = sources / "profile"
    wheelhouse = sources / "wheels"

    def inventory(names):
        values = []
        for name in names:
            path = wheelhouse / (name + "-fixture.whl")
            path.write_bytes(b"synthetic source inventory; never installed")
            values.append(
                {
                    "name": name,
                    "version": "fixture",
                    "filename": path.name,
                    "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                    "downloadBytes": path.stat().st_size,
                }
            )
        return values

    core = json.loads((profiles / "easyai-cpu-sources.json").read_bytes())
    core["packages"] += inventory(["numpy", "pillow", "packaging", "networkx"])
    (profiles / "easyai-cpu-sources.json").write_text(json.dumps(core))
    for group, names, dependencies, header in [
        ("ml", ["scipy"], {"scipy": ["numpy"]}, ML_HEADER),
        (
            "cv",
            ["scikit-image", "imageio", "tifffile", "lazy-loader"],
            json.loads((PROFILE_ROOT / "easyai-cv-sources.json").read_bytes())["dependencies"],
            CV_HEADER,
        ),
    ]:
        values = inventory(names)
        (profiles / f"easyai-{group}-sources.json").write_text(
            json.dumps({"packages": values, "dependencies": dependencies})
        )
        (profiles / f"easyai-{group}-linux-cp311.lock").write_text(
            header
            + "".join(
                f"{w['name']}==fixture \\\n    --hash=sha256:{w['sha256']}\n"
                for w in sorted(values, key=lambda w: w["name"])
            )
        )
    runtime = InstallRuntime(app)
    core_only = runtime.snapshot()
    cv = runtime.snapshot({"scikit-image"})
    assert cv.enabled and cv.fingerprint != core_only.fingerprint
    path = wheelhouse / "imageio-fixture.whl"
    original = path.read_bytes()
    path.write_bytes(b"changed")
    with pytest.raises(ValueError):
        runtime.snapshot({"scikit-image"})
    assert runtime.snapshot().fingerprint == core_only.fingerprint
    path.write_bytes(original)
    core_size = sum(w["downloadBytes"] for w in core["packages"]) + sum(
        a["bytes"] for a in config["bootstrap"]
    )
    config["diskBudgetBytes"] = core_size
    (app / "install-runtime.json").write_text(json.dumps(config))
    assert runtime.snapshot().enabled
    with pytest.raises(ValueError, match="INSTALL_DISK_BUDGET_EXCEEDED"):
        runtime.snapshot({"scikit-image"})


def test_cv_source_or_lock_drift_invalidates_constraints(tmp_path):
    for path in PROFILE_ROOT.iterdir():
        if path.suffix in {".json", ".lock"}:
            (tmp_path / path.name).write_bytes(path.read_bytes())
    before = constraints_hash(tmp_path)
    path = tmp_path / "easyai-cv-sources.json"
    data = json.loads(path.read_bytes())
    data["packages"][0]["downloadBytes"] += 1
    path.write_text(json.dumps(data))
    assert constraints_hash(tmp_path) != before
    path = tmp_path / "easyai-cv-linux-cp311.lock"
    path.write_bytes(path.read_bytes() + b"opencv-python-headless==1\n")
    with pytest.raises(ValueError, match="INSTALL_DEPENDENCIES_UNRESOLVED"):
        wheels(tmp_path, {"scikit-image"})
