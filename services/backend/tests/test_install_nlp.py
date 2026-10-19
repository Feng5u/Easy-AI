"""Reviewed NLP metadata and synthetic contracts; never packages/corpora/model execution."""

import ast
import hashlib
import json
import threading

import pytest
from packaging.markers import default_environment
from packaging.requirements import Requirement
from packaging.specifiers import SpecifierSet
from packaging.utils import canonicalize_name, parse_wheel_filename
from packaging.tags import cpython_tags, compatible_tags
from easyai.domain.install import (
    InstallPlanRequest,
    InstallSourceRequest,
    InstallSourceConfirmation,
)
from easyai.services import install_source_selection as source_module
from easyai.services import install_service as service_module
from easyai.services.install_process import OfflineWheelInstaller, inspection_source
from easyai.services.install_runtime import InstallRuntime
from easyai.services.install_service import PROFILE_ROOT, InstallService, digest
from easyai.services.install_sources import (
    NLP_HEADER,
    UNSUPPORTED,
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
    monkeypatch.setattr("subprocess.Popen", lambda *a, **k: pytest.fail("No NLP execution"))
    monkeypatch.setattr("socket.create_connection", lambda *a, **k: pytest.fail("No NLP network"))


def request(ids):
    return InstallPlanRequest(
        target_id="local",
        profile_id="easyai-cpu",
        package_ids=ids,
        new_environment_spec={"name": "nlp"},
    )


def test_nlp_pep658_closure_and_rejections_match_fixed_cpu():
    data = json.loads((PROFILE_ROOT / "easyai-nlp-sources.json").read_bytes())
    selected = wheels(PROFILE_ROOT, {"sentencepiece"})
    versions = {w["name"]: w["version"] for w in selected}
    assert len(selected) == len(wheels(PROFILE_ROOT)) + 1 == 22
    assert data["dependencies"]["sentencepiece"] == []
    assert len(data["packages"]) == 48
    assert (
        next(w for w in data["packages"] if w["name"] == "sentencepiece")["downloadBytes"]
        == 1394242
    )
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
    known = {
        w["name"]: w["version"]
        for w in wheels(
            PROFILE_ROOT, {"scipy", "pytorch-lightning", "spacy", "transformers", "gensim"}
        )
    }
    platforms = [f"manylinux_2_{n}_x86_64" for n in range(28, 4, -1)] + [
        "manylinux2014_x86_64",
        "manylinux2010_x86_64",
        "manylinux1_x86_64",
    ]
    target_tags = set(cpython_tags((3, 11), abis=["cp311"], platforms=platforms)) | set(
        compatible_tags((3, 11), interpreter="cp311", platforms=platforms)
    )
    assert not (parse_wheel_filename("invalid-1.0-cp312-cp312-win_amd64.whl")[3] & target_tags)
    for package in data["packages"] + data["rejectedCandidates"]:
        assert SpecifierSet(package["requiresPython"]).contains("3.11.17")
        name, version, _, tags = parse_wheel_filename(package["filename"])
        assert name == canonicalize_name(package["name"]) and str(version) == package["version"]
        assert tags & target_tags
        assert package["unpackedBytes"] is None and not package["yanked"]
        assert package["metadataUrl"] == package["url"] + ".metadata"
        assert (
            package["releaseJsonUrl"]
            == f"https://pypi.org/pypi/{package['name']}/{package['version']}/json"
        )
        assert all(len(package[k]) == 64 for k in ["sha256", "metadataSha256", "releaseJsonSha256"])
        active = []
        for raw in package["requiresDist"]:
            dep = Requirement(raw)
            if dep.marker and not dep.marker.evaluate(env):
                continue
            assert not dep.url and not dep.extras
            key = canonicalize_name(dep.name)
            if key in known:
                assert dep.specifier.contains(known[key])  # No invented direct CPU-pin conflict.
            active.append(key)
        if package["name"] == "sentencepiece":
            assert not active and not package["knownVulnerabilitiesAtCapture"]
            assert versions[package["name"]] == "0.2.2"
        elif "reason" not in package:
            assert not package["knownVulnerabilitiesAtCapture"]
            assert known[package["name"]] == package["version"]
            assert set(active) == set(data["dependencies"][package["name"]])
        else:
            assert active and package["reason"] == UNSUPPORTED[package["name"]]
    nltk = next(x for x in data["rejectedCandidates"] if x["name"] == "nltk")
    advisory = nltk["knownVulnerabilitiesAtCapture"][0]
    assert (
        advisory["id"] == "GHSA-8mgp-746c-j5xp"
        and not advisory["fixed_in"]
        and not advisory["withdrawn"]
    )
    assert versions["torch"] == "2.10.0+cpu" and versions["numpy"] == "2.4.2"


def test_single_mixed_and_whole_nlp_group_share_plan_and_budget(tmp_path):
    service = InstallService(tmp_path, runtime=InstallRuntime(tmp_path))
    try:
        for ids in [
            ["sentencepiece"],
            ["torch", "sentencepiece"],
            ["sentencepiece", "scikit-image", "pytorch-lightning"],
            ["spacy"],
            ["transformers"],
            ["gensim"],
            [
                "sentencepiece",
                "spacy",
                "transformers",
                "gensim",
                "pytorch-lightning",
                "scikit-image",
            ],
        ]:
            plan = service.plan(request(ids))
            records = wheels(PROFILE_ROOT, set(ids))
            assert not plan.blockers and not plan.execution_enabled
            assert {c.package_id: c.target_version for c in plan.package_changes} == {
                w["name"]: w["version"] for w in records
            }
            assert len(records) == len({w["name"] for w in records})
            assert plan.download_bytes == sum(w["downloadBytes"] for w in records)
            assert plan.installed_bytes is None
            assert plan.plan_hash == digest(plan.model_dump(exclude={"plan_hash"}))
        cards = {c.package_id: c for c in service.catalog().packages}
        assert cards["sentencepiece"].target_version == "0.2.2"
        assert sum(c.target_version is not None for c in cards.values()) == 14
        for name in ["nltk", "hanlp"]:
            plan = service.plan(request([name]))
            assert cards[name].target_version is None and UNSUPPORTED[name] in plan.blockers
            assert (
                not plan.execution_enabled and plan.download_bytes is plan.installed_bytes is None
            )
            with pytest.raises(ValueError, match="INSTALL_PLAN_BLOCKED"):
                service.confirm(confirmation(plan))
            with pytest.raises(ValueError, match=UNSUPPORTED[name]):
                service.preview_sources(
                    InstallSourceRequest(manifest_path="/never-read", package_ids=[name])
                )
        group = service.plan(
            request(["nltk", "spacy", "sentencepiece", "transformers", "gensim", "hanlp"])
        )
        assert group.blockers and not group.execution_enabled and group.download_bytes is None
        assert lock_bytes(PROFILE_ROOT, {"sentencepiece"}) == lock_bytes(
            PROFILE_ROOT, {"torch", "sentencepiece"}
        )
    finally:
        service.close()


def test_nlp_selected_source_registration_missing_and_budget_gates(configured, monkeypatch):
    app, sources, config = configured
    profiles, wheelhouse = sources / "profile", sources / "wheels"
    raw = b"synthetic inventory, never an executable wheel"
    extra = wheelhouse / "sentencepiece-fixture.whl"
    extra.write_bytes(raw)
    package = dict(
        name="sentencepiece",
        version="fixture",
        filename=extra.name,
        sha256=hashlib.sha256(raw).hexdigest(),
        downloadBytes=len(raw),
    )
    (profiles / "easyai-nlp-sources.json").write_text(
        json.dumps({"packages": [package], "dependencies": {"sentencepiece": []}})
    )
    (profiles / "easyai-nlp-linux-cp311.lock").write_text(
        NLP_HEADER + f"sentencepiece==fixture \\\n    --hash=sha256:{package['sha256']}\n"
    )
    runtime = InstallRuntime(app)
    baseline = runtime.snapshot()
    assert runtime.snapshot({"sentencepiece"}).enabled
    extra.unlink()
    with pytest.raises(FileNotFoundError):
        runtime.snapshot({"sentencepiece"})
    assert runtime.snapshot().fingerprint == baseline.fingerprint
    extra.write_bytes(raw)
    monkeypatch.setattr(source_module, "PROFILE_ROOT", profiles)
    path = sources / "nlp-source.json"
    path.write_text(json.dumps(config))
    path.chmod(0o600)
    service = InstallService(app, runtime=runtime)
    try:
        preview = service.preview_sources(
            InstallSourceRequest(manifest_path=str(path), package_ids=["sentencepiece"])
        )
        assert (
            len(preview.wheels) == 2
            and not preview.execution_enabled
            and preview.installed_bytes is None
        )
        assert preview.source_bytes == sum(w.bytes for w in preview.wheels + preview.bootstrap)
        result = service.confirm_sources(
            InstallSourceConfirmation(
                preview_id=preview.preview_id, preview_hash=preview.preview_hash, confirmed=True
            )
        )
        assert not result.execution_enabled and not runtime.snapshot({"sentencepiece"}).enabled
        assert not json.loads(runtime.configuration_path.read_bytes())["executionAuthorized"]
    finally:
        service.close()
    core = json.loads((profiles / "easyai-cpu-sources.json").read_bytes())["packages"]
    config["diskBudgetBytes"] = sum(w["downloadBytes"] for w in core) + sum(
        a["bytes"] for a in config["bootstrap"]
    )
    runtime.configuration_path.write_text(json.dumps(config))
    assert runtime.snapshot().enabled
    with pytest.raises(ValueError, match="INSTALL_DISK_BUDGET_EXCEEDED"):
        runtime.snapshot({"sentencepiece"})


def test_nlp_metadata_and_lock_drift_bind_constraints_and_confirmation(tmp_path, monkeypatch):
    for path in PROFILE_ROOT.iterdir():
        if path.is_file():
            (tmp_path / path.name).write_bytes(path.read_bytes())
    monkeypatch.setattr(service_module, "PROFILE_ROOT", tmp_path)
    (tmp_path / "app").mkdir()
    service = InstallService(tmp_path / "app")
    try:
        plan = service.plan(request(["sentencepiece"]))
        before = constraints_hash(tmp_path)
        path = tmp_path / "easyai-nlp-sources.json"
        data = json.loads(path.read_bytes())
        data["packages"][0]["downloadBytes"] += 1
        path.write_text(json.dumps(data))
        assert constraints_hash(tmp_path) != before
        with pytest.raises(ValueError, match="INSTALL_PLAN_STALE"):
            service.confirm(confirmation(plan))
        lock = tmp_path / "easyai-nlp-linux-cp311.lock"
        lock.write_bytes(lock.read_bytes() + b"unreviewed==1\n")
        with pytest.raises(ValueError, match="INSTALL_DEPENDENCIES_UNRESOLVED"):
            wheels(tmp_path, {"sentencepiece"})
        assert wheels(tmp_path) == wheels(PROFILE_ROOT)
    finally:
        service.close()


def test_same_installer_consumes_nlp_lock_and_selected_probe_only(tmp_path):
    service = InstallService(tmp_path)
    plan = service.plan(request(["sentencepiece"]))
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

        def run(self, argv, *args):
            compile(argv[-1], "<captured-nlp-pip>", "exec")
            calls.append(argv[-1])
            return "completed", []

    try:
        installer = OfflineWheelInstaller(Commands(), tmp_path, authorized=True)
        assert installer.install(prefix, plan, threading.Event(), lambda: None) == "completed"
        exact = next(command_root.glob("*.lock")).read_bytes()
        assert exact == lock_bytes(PROFILE_ROOT, {"sentencepiece"})
        assert exact.count(b"sentencepiece==") == 1 and b"nltk==" not in exact
        assert "--no-index" in calls[0] and "--require-hashes" in calls[0]
        for selected in [{"torch"}, {w["name"] for w in wheels(PROFILE_ROOT, {"sentencepiece"})}]:
            source = inspection_source("nonce", required_imports(selected))
            tree = ast.parse(source)
            loops = [n for n in tree.body if isinstance(n, ast.For)]
            imports = ast.literal_eval(loops[1].iter)
            assert ("sentencepiece" in imports) is ("sentencepiece" in selected)
            assert not set(imports).intersection(
                {"nltk", "spacy", "transformers", "gensim", "hanlp"}
            )
            assert ".download(" not in source and "from_pretrained" not in source
    finally:
        service.close()


@pytest.mark.parametrize("root", ["sentencepiece", "spacy", "transformers", "gensim"])
@pytest.mark.parametrize("failure", [None, "import", "version", "tensor"])
def test_nlp_final_import_version_and_tensor_fail_closed(owned, failure, root):
    service, _, old, _, inventory, original = owned
    service.cancel(old.job_id)
    raw = original.model_dump()
    raw["package_ids"] = [root]
    plan = service.plan(InstallPlanRequest(**raw))
    job = service.confirm(confirmation(plan))

    class Installer:
        def install(self, *args):
            versions = {c.package_id: c.target_version for c in plan.package_changes}
            imports = dict.fromkeys(required_imports(set(versions)), True)
            if failure == "import":
                imports[root] = False
            if failure == "version":
                versions[root] = "0.0.1"
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


def test_all_default_closures_and_provider_pins_are_exact_without_unselected_http():
    from itertools import combinations
    from easyai.services.install_sources import OPTIONAL_ROOTS

    data = json.loads((PROFILE_ROOT / "easyai-nlp-sources.json").read_bytes())
    assert (PROFILE_ROOT / "easyai-nlp-sources.json").stat().st_size < 100000
    base = {r["name"]: r for r in wheels(PROFILE_ROOT)}
    for root, count in [("spacy", 60), ("transformers", 43), ("gensim", 25)]:
        records = wheels(PROFILE_ROOT, {root})
        assert len(records) == data["defaultClosures"][root]["plannedWheelCount"] == count
        assert (
            sum(r["downloadBytes"] for r in records if r["name"] not in base)
            == data["defaultClosures"][root]["addedToCoreBytes"]
        )
        assert not any(r["name"] == "aiohttp" for r in records)
        assert not data["defaultClosures"][root]["modelApisEnabled"]
        assert not data["defaultClosures"][root]["offlineImportVerified"]
    roots = sorted(OPTIONAL_ROOTS)
    for size in range(len(roots) + 1):
        for choice in combinations(roots, size):
            selected = set(choice)
            records = wheels(PROFILE_ROOT, selected)
            observed = {r["name"]: r for r in records}
            assert len(records) == len(observed)
            assert all(observed[n] == r for n, r in base.items())
            assert selected <= observed.keys()
            assert ("aiohttp" in observed) is ("pytorch-lightning" in selected)
            for r in data["packages"]:
                if r["name"] in observed:
                    assert set(data["dependencies"][r["name"]]) <= observed.keys()
    missing = data["blockedDependencies"]
    assert set(missing) == {"hanlp-common", "hanlp-downloader", "hanlp-trie"}
    assert not data["defaultClosures"]["hanlp"]["closureVerified"]
    assert data["defaultClosures"]["hanlp"]["plannedWheelCount"] is None
    assert data["defaultClosures"]["hanlp"]["addedToCoreBytes"] is None
    for evidence in missing.values():
        assert len(evidence["releaseJsonSha256"]) == 64
        assert evidence["reason"] == "INSTALL_BINARY_WHEEL_UNAVAILABLE"
        assert evidence["artifacts"] and all(
            a["packagetype"] == "sdist" for a in evidence["artifacts"]
        )


def test_extended_nlp_selected_sources_use_provider_closure_and_preserve_execution_gate(
    configured, monkeypatch
):
    from easyai.services.install_sources import ML_HEADER, CV_HEADER, DL_HEADER

    app, sources, config = configured
    profiles, wheelhouse = sources / "profile", sources / "wheels"
    for group, header in [
        ("cpu", ""),
        ("ml", ML_HEADER),
        ("cv", CV_HEADER),
        ("dl", DL_HEADER),
        ("nlp", NLP_HEADER),
    ]:
        value = json.loads((PROFILE_ROOT / f"easyai-{group}-sources.json").read_bytes())
        synthetic = []
        for record in value["packages"]:
            path = wheelhouse / (record["name"] + "-fixture.whl")
            path.write_bytes(b"synthetic non-executable source inventory")
            synthetic.append(
                {
                    "name": record["name"],
                    "version": record["version"],
                    "filename": path.name,
                    "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                    "downloadBytes": path.stat().st_size,
                }
            )
        value["packages"] = synthetic
        (profiles / f"easyai-{group}-sources.json").write_text(json.dumps(value))
        lock = "".join(
            f"{r['name']}=={r['version']} \\\n    --hash=sha256:{r['sha256']}\n"
            for r in sorted(synthetic, key=lambda r: r["name"])
        )
        (profiles / f"easyai-{group}-linux-cp311.lock").write_text(header + lock)
    runtime = InstallRuntime(app)
    baseline = runtime.snapshot()
    monkeypatch.setattr(source_module, "PROFILE_ROOT", profiles)
    source = sources / "all-nlp.json"
    source.write_text(json.dumps(config))
    source.chmod(0o600)
    service = InstallService(app, runtime=runtime)
    try:
        for root, count in [("spacy", 60), ("transformers", 43), ("gensim", 25)]:
            assert runtime.snapshot({root}).enabled
            preview = service.preview_sources(
                InstallSourceRequest(manifest_path=str(source), package_ids=[root])
            )
            assert len(preview.wheels) == count and not preview.execution_enabled
            assert preview.source_bytes == sum(w.bytes for w in preview.wheels + preview.bootstrap)
            path = wheelhouse / (root + "-fixture.whl")
            raw = path.read_bytes()
            path.unlink()
            with pytest.raises(FileNotFoundError):
                runtime.snapshot({root})
            assert runtime.snapshot().fingerprint == baseline.fingerprint
            path.write_bytes(raw)
        preview = service.preview_sources(
            InstallSourceRequest(
                manifest_path=str(source), package_ids=["spacy", "transformers", "gensim"]
            )
        )
        result = service.confirm_sources(
            InstallSourceConfirmation(
                preview_id=preview.preview_id, preview_hash=preview.preview_hash, confirmed=True
            )
        )
        assert not result.execution_enabled
        assert not json.loads(runtime.configuration_path.read_bytes())["executionAuthorized"]
        assert not runtime.snapshot({"spacy", "transformers", "gensim"}).enabled
    finally:
        service.close()
    core = json.loads((profiles / "easyai-cpu-sources.json").read_bytes())["packages"]
    config["diskBudgetBytes"] = sum(w["downloadBytes"] for w in core) + sum(
        a["bytes"] for a in config["bootstrap"]
    )
    runtime.configuration_path.write_text(json.dumps(config))
    assert runtime.snapshot().enabled
    for root in ["spacy", "transformers", "gensim"]:
        with pytest.raises(ValueError, match="INSTALL_DISK_BUDGET_EXCEEDED"):
            runtime.snapshot({root})


@pytest.mark.parametrize(
    "root,module", [("spacy", "spacy"), ("transformers", "transformers"), ("gensim", "gensim")]
)
def test_extended_nlp_fixed_commands_probe_only_selected_imports_not_model_apis(
    tmp_path, root, module
):
    service = InstallService(tmp_path)
    try:
        plan = service.plan(request([root]))
        prefix = service.root / plan.environment_id
        (prefix / "bin").mkdir(parents=True)
        (prefix / "bin/python").write_text("not executed")
        (prefix / ".easyai-owned.json").write_text(
            json.dumps({"ownedByEasyAI": True, "environmentId": plan.environment_id})
        )
        command_root = tmp_path / "captured"
        command_root.mkdir()
        calls = []

        class Commands:
            root = command_root

            def run(self, argv, *args):
                calls.append(argv[-1])
                compile(argv[-1], "<captured-nlp>", "exec")
                return "completed", []

        assert (
            OfflineWheelInstaller(Commands(), tmp_path, authorized=True).install(
                prefix, plan, threading.Event(), lambda: None
            )
            == "completed"
        )
        assert next(command_root.glob("*.lock")).read_bytes() == lock_bytes(PROFILE_ROOT, {root})
        assert (
            "--no-index" in calls[0]
            and "--only-binary=:all:" in calls[0]
            and "--require-hashes" in calls[0]
        )
        names = {w["name"] for w in wheels(PROFILE_ROOT, {root})}
        source = inspection_source("nonce", required_imports(names))
        tree = ast.parse(source)
        loops = [n for n in tree.body if isinstance(n, ast.For)]
        imports = ast.literal_eval(loops[1].iter)
        assert module in imports and set(imports) == set(required_imports(names))
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                assert not isinstance(node.func, ast.Attribute) or node.func.attr not in {
                    "load",
                    "download",
                    "from_pretrained",
                    "pipeline",
                }
                assert not isinstance(node.func, ast.Name) or node.func.id not in {
                    "pipeline",
                    "from_pretrained",
                }
        unselected = inspection_source("nonce", required_imports({"torch"}))
        tree = ast.parse(unselected)
        loops = [n for n in tree.body if isinstance(n, ast.For)]
        assert not {"spacy", "transformers", "gensim"}.intersection(ast.literal_eval(loops[1].iter))
    finally:
        service.close()
