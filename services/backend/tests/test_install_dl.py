"""Read-only metadata and synthetic DL contracts; no wheel/install/import/ABI run."""

import ast
import hashlib
import json
import threading

import pytest
from packaging.markers import default_environment
from packaging.requirements import Requirement
from packaging.specifiers import SpecifierSet
from packaging.utils import canonicalize_name, parse_wheel_filename
from easyai.domain.install import (
    InstallPlanRequest,
    InstallSourceRequest,
    InstallSourceConfirmation,
)
from easyai.services import install_source_selection as source_module
from easyai.services.install_process import ManagedInstallInspector, OfflineWheelInstaller
from easyai.services.install_runtime import InstallRuntime
from easyai.services.install_service import PROFILE_ROOT, InstallService, ProbeReceipt
from easyai.services.install_sources import (
    DL_HEADER,
    IMPORTS,
    constraints_hash,
    lock_bytes,
    required_imports,
    wheels,
)
from test_install_runtime import configured as configured_fixture
from test_install_process import owned as owned_fixture
from test_install_service import confirmation

configured = configured_fixture
owned = owned_fixture


@pytest.fixture(autouse=True)
def no_execution(monkeypatch):
    monkeypatch.setattr(
        "subprocess.Popen", lambda *a, **k: pytest.fail("Never execute DL tools or imports")
    )
    monkeypatch.setattr(
        "socket.create_connection", lambda *a, **k: pytest.fail("Never connect in DL fixtures")
    )


def request(ids):
    return InstallPlanRequest(
        target_id="local",
        profile_id="easyai-cpu",
        package_ids=ids,
        new_environment_spec={"name": "dl"},
    )


def test_dl_metadata_complete_closure_and_core_http_extra_match_fixed_cpu():
    data = json.loads((PROFILE_ROOT / "easyai-dl-sources.json").read_bytes())
    selected = wheels(PROFILE_ROOT, {"pytorch-lightning"})
    versions = {w["name"]: w["version"] for w in selected}
    base = {w["name"]: w for w in wheels(PROFILE_ROOT)}
    assert len(data["packages"]) == 14 and len(selected) == len(base) + 14
    assert data["activatedCoreExtras"] == {"fsspec": ["http"]}
    assert sum(w["downloadBytes"] for w in data["packages"]) == 5909314
    env = default_environment()
    env.update(
        python_version="3.11",
        python_full_version="3.11.17",
        sys_platform="linux",
        os_name="posix",
        platform_system="Linux",
        platform_machine="x86_64",
        platform_python_implementation="CPython",
        implementation_name="cpython",
        extra="",
    )
    for package in data["packages"] + data["coreExtraMetadata"]:
        assert SpecifierSet(package["requiresPython"]).contains("3.11.17")
        assert package["yanked"] is False and not package["knownVulnerabilitiesAtCapture"]
        assert package["unpackedBytes"] is None and package["downloadBytes"] > 0
        name, version, _, tags = parse_wheel_filename(package["filename"])
        assert name == canonicalize_name(package["name"]) and str(version) == package["version"]
        assert any(
            t.platform == "any" or (t.interpreter == "cp311" and t.platform.endswith("x86_64"))
            for t in tags
        )
        assert package["metadataUrl"] == package["url"] + ".metadata"
        assert (
            package["releaseJsonUrl"]
            == f"https://pypi.org/pypi/{package['name']}/{package['version']}/json"
        )
        assert all(
            len(package[key]) == 64 for key in ["sha256", "metadataSha256", "releaseJsonSha256"]
        )
        extras = {""} | set(data["activatedCoreExtras"].get(package["name"], []))
        active = []
        for raw in package["requiresDist"]:
            dep = Requirement(raw)
            if dep.marker and not any(
                dep.marker.evaluate({**env, "extra": extra}) for extra in extras
            ):
                continue
            assert not dep.url
            key = canonicalize_name(dep.name)
            assert key in versions and dep.specifier.contains(versions[key])
            assert not dep.extras or (key == "fsspec" and dep.extras == {"http"})
            active.append(key)
        assert set(active) == set(data["dependencies"][package["name"]])
        if package["name"] in base:
            assert all(
                package[k] == base[package["name"]][k]
                for k in ["version", "filename", "url", "sha256", "downloadBytes"]
            )
    assert versions["torch"] == "2.10.0+cpu" and versions["torchvision"] == "0.25.0+cpu"
    assert versions["fsspec"] == "2026.9.0" and versions["packaging"] == "26.3"
    assert {w["name"] for w in data["packages"]} <= IMPORTS.keys()


def test_single_and_dl_group_share_deduplicated_closure_without_core_upgrade(tmp_path):
    service = InstallService(tmp_path)
    try:
        expected = wheels(PROFILE_ROOT, {"pytorch-lightning"})
        for ids in [["pytorch-lightning"], ["torch", "torchvision", "pytorch-lightning"]]:
            value = service.plan(request(ids))
            assert not value.blockers and not value.execution_enabled
            assert (
                len(value.package_changes)
                == len({p.package_id for p in value.package_changes})
                == 35
            )
            assert {p.package_id: p.target_version for p in value.package_changes} == {
                w["name"]: w["version"] for w in expected
            }
            assert {p.package_id for p in value.package_changes if p.requested} == set(ids)
            assert value.download_bytes == sum(w["downloadBytes"] for w in expected)
            assert value.installed_bytes is None
        assert lock_bytes(PROFILE_ROOT, {"pytorch-lightning"}) == lock_bytes(
            PROFILE_ROOT, {"torch", "torchvision", "pytorch-lightning"}
        )
        mixed = wheels(PROFILE_ROOT, {"pytorch-lightning", "scikit-image", "scikit-learn"})
        assert len(mixed) == len({w["name"] for w in mixed})
        assert len([p for p in service.catalog().packages if p.target_version]) == 11
    finally:
        service.close()


def test_selected_dl_sources_budget_and_registration_include_http_closure(configured, monkeypatch):
    app, sources, config = configured
    profiles, wheelhouse = sources / "profile", sources / "wheels"
    data = json.loads((PROFILE_ROOT / "easyai-dl-sources.json").read_bytes())

    def inventory(names):
        result = []
        for name in names:
            path = wheelhouse / (name + "-fixture.whl")
            path.write_bytes(b"synthetic inventory only, never a wheel")
            result.append(
                {
                    "name": name,
                    "version": "fixture",
                    "filename": path.name,
                    "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                    "downloadBytes": path.stat().st_size,
                }
            )
        return result

    core = json.loads((profiles / "easyai-cpu-sources.json").read_bytes())
    core["packages"] += inventory(["fsspec", "numpy", "packaging", "typing-extensions"])
    (profiles / "easyai-cpu-sources.json").write_text(json.dumps(core))
    additions = inventory([w["name"] for w in data["packages"]])
    (profiles / "easyai-dl-sources.json").write_text(
        json.dumps({"packages": additions, "dependencies": data["dependencies"]})
    )
    (profiles / "easyai-dl-linux-cp311.lock").write_text(
        DL_HEADER
        + "".join(
            f"{w['name']}==fixture \\\n    --hash=sha256:{w['sha256']}\n"
            for w in sorted(additions, key=lambda w: w["name"])
        )
    )
    runtime = InstallRuntime(app)
    baseline = runtime.snapshot()
    selected = runtime.snapshot({"pytorch-lightning"})
    assert selected.enabled and selected.fingerprint != baseline.fingerprint
    path = wheelhouse / "aiohttp-fixture.whl"
    content = path.read_bytes()
    path.unlink()
    with pytest.raises(FileNotFoundError):
        runtime.snapshot({"pytorch-lightning"})
    assert runtime.snapshot().fingerprint == baseline.fingerprint
    path.write_bytes(content)
    monkeypatch.setattr(source_module, "PROFILE_ROOT", profiles)
    source = sources / "lightning-source.json"
    source.write_text(json.dumps(config))
    source.chmod(0o600)
    service = InstallService(app, runtime=runtime)
    try:
        preview = service.preview_sources(
            InstallSourceRequest(manifest_path=str(source), package_ids=["pytorch-lightning"])
        )
        assert len(preview.wheels) == 19 and not preview.execution_enabled
        assert preview.disk_budget_bytes == config["diskBudgetBytes"]
        result = service.confirm_sources(
            InstallSourceConfirmation(
                preview_id=preview.preview_id, preview_hash=preview.preview_hash, confirmed=True
            )
        )
        assert (
            not result.execution_enabled
            and not json.loads(runtime.configuration_path.read_bytes())["executionAuthorized"]
        )
        assert not runtime.snapshot({"pytorch-lightning"}).enabled
    finally:
        service.close()
    config["diskBudgetBytes"] = sum(w["downloadBytes"] for w in core["packages"]) + sum(
        a["bytes"] for a in config["bootstrap"]
    )
    (app / "install-runtime.json").write_text(json.dumps(config))
    assert runtime.snapshot().enabled
    with pytest.raises(ValueError, match="INSTALL_DISK_BUDGET_EXCEEDED"):
        runtime.snapshot({"pytorch-lightning"})


def test_existing_installer_consumes_exact_dl_hash_lock(tmp_path):
    service = InstallService(tmp_path)
    plan = service.plan(request(["pytorch-lightning"]))
    prefix = service.root / plan.environment_id
    (prefix / "bin").mkdir(parents=True)
    (prefix / "bin/python").write_text("never executed")
    (prefix / ".easyai-owned.json").write_text(
        json.dumps({"ownedByEasyAI": True, "environmentId": plan.environment_id})
    )
    command_root = tmp_path / "commands"
    command_root.mkdir()
    calls = []

    class Commands:
        root = command_root

        def run(self, argv, cwd, cancel, progress):
            compile(argv[-1], "<captured-fixed-pip>", "exec")
            calls.append(argv)
            return "completed", []

    try:
        installer = OfflineWheelInstaller(Commands(), tmp_path, authorized=True)
        assert installer.install(prefix, plan, threading.Event(), lambda: None) == "completed"
        exact = next(command_root.glob("*.lock")).read_bytes()
        assert exact == lock_bytes(PROFILE_ROOT, {"pytorch-lightning"})
        assert (
            exact.count(b"fsspec==")
            == exact.count(b"aiohttp==")
            == exact.count(b"pytorch-lightning==")
            == 1
        )
        assert "--no-index" in calls[0][-1] and "--require-hashes" in calls[0][-1]
    finally:
        service.close()


def test_dl_drift_and_core_override_refused_without_affecting_unselected_core(tmp_path):
    for path in PROFILE_ROOT.iterdir():
        if path.suffix in {".json", ".lock"}:
            (tmp_path / path.name).write_bytes(path.read_bytes())
    before = constraints_hash(tmp_path)
    path = tmp_path / "easyai-dl-sources.json"
    data = json.loads(path.read_bytes())
    data["packages"][0]["downloadBytes"] += 1
    path.write_text(json.dumps(data))
    assert constraints_hash(tmp_path) != before
    lock = tmp_path / "easyai-dl-linux-cp311.lock"
    original = lock.read_bytes()
    lock.write_bytes(original + b"unreviewed==1\n")
    with pytest.raises(ValueError, match="INSTALL_DEPENDENCIES_UNRESOLVED"):
        wheels(tmp_path, {"pytorch-lightning"})
    lock.write_bytes(original)
    data["packages"].append({**data["packages"][0], "name": "torch", "version": "999"})
    path.write_text(json.dumps(data))
    lock.write_text(
        DL_HEADER
        + "".join(
            f"{w['name']}=={w['version']} \\\n    --hash=sha256:{w['sha256']}\n"
            for w in sorted(data["packages"], key=lambda w: w["name"])
        )
    )
    with pytest.raises(ValueError, match="INSTALL_DEPENDENCIES_UNRESOLVED"):
        wheels(tmp_path, {"pytorch-lightning"})
    path.unlink()
    lock.unlink()
    assert wheels(tmp_path, {"torch"}) == wheels(PROFILE_ROOT)


def test_existing_lightning_version_conflict_blocks_confirmation(owned):
    service, _, job, _, inventory, original = owned
    service.cancel(job.job_id)
    inventory.write_text(
        json.dumps({"versions": {"pytorch-lightning": "0.0.1"}, "imports": {}, "tensor_ok": False})
    )
    raw = original.model_dump()
    raw["package_ids"] = ["pytorch-lightning"]
    plan = service.plan(InstallPlanRequest(**raw))
    assert "INSTALL_VERSION_CONFLICT" in plan.blockers and not plan.execution_enabled
    with pytest.raises(ValueError, match="INSTALL_PLAN_BLOCKED"):
        service.confirm(confirmation(plan))


@pytest.mark.parametrize("failure", [None, "root-import", "http-import", "version", "tensor"])
def test_final_dl_version_import_tensor_gates_are_mandatory(owned, failure):
    service, _, old, _, inventory, original = owned
    service.cancel(old.job_id)
    raw = original.model_dump()
    raw["package_ids"] = ["pytorch-lightning"]
    plan = service.plan(InstallPlanRequest(**raw))
    job = service.confirm(confirmation(plan))

    class Installer:
        def install(self, *args):
            versions = {c.package_id: c.target_version for c in plan.package_changes}
            imports = dict.fromkeys(required_imports(set(versions)), True)
            if failure == "root-import":
                imports["pytorch_lightning"] = False
            if failure == "http-import":
                imports["fsspec.implementations.http"] = False
            if failure == "version":
                versions["torchmetrics"] = "0.0.1"
            inventory.write_text(
                json.dumps(
                    {"versions": versions, "imports": imports, "tensor_ok": failure != "tensor"}
                )
            )
            return "completed"

    result = service.execute(job.job_id, Installer())
    assert result.state == ("SUCCEEDED" if failure is None else "FAILED")
    assert result.verified is (failure is None) and result.needs_reprobe is (failure is not None)
    assert job.job_id not in service._leases


def test_fixed_probe_does_not_import_dl_or_http_when_unselected(tmp_path):
    prefix = tmp_path / "prefix"
    (prefix / "bin").mkdir(parents=True)
    (prefix / "bin/python").write_text("never executed")
    seen = []

    class Captured(Exception):
        pass

    class Commands:
        def run(self, argv, *args, **kwargs):
            tree = ast.parse(argv[-1])
            loops = [node for node in tree.body if isinstance(node, ast.For)]
            seen.append(ast.literal_eval(loops[1].iter))
            raise Captured

    inspector = ManagedInstallInspector(Commands())
    for selected in [{"torch"}, {w["name"] for w in wheels(PROFILE_ROOT, {"pytorch-lightning"})}]:
        with pytest.raises(Captured):
            inspector.inspect_owned(
                prefix, "nonce", ProbeReceipt(import_names=required_imports(selected))
            )
    assert seen[0] == ("torch",) and not any(
        "lightning" in name or "http" in name for name in seen[0]
    )
    assert {
        "pytorch_lightning",
        "torchmetrics",
        "yaml",
        "aiohttp",
        "fsspec.implementations.http",
    } <= set(seen[1])
