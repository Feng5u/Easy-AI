"""Real helper/client protocol with explicitly substituted stdlib synthetic children.

The bootstrap/pip/probe sources are captured, NEVER executed. The only real child
prints synthetic protocol reports. Actual filesystem source hashes, allocation,
owner locking, journal and stdlib child exit proof are exercised, not package ABI.
"""

import ast
import copy
from datetime import datetime
import hashlib
import json
from pathlib import Path
import sys
import threading

import pytest
from uuid import uuid4

from easyai.domain.connections import SessionControl
from easyai.domain.install import InstallPlanRequest, InstallConfirmation, InstallTargetIdentity
from easyai.services.install_service import InstallService, PROFILE_ROOT
from easyai.services.remote_install import RemoteConfiguration, RemoteInstallTarget
from test_remote_install_owner import owner as owner_fixture, payload as payload_fixture

owner = owner_fixture
payload = payload_fixture


@pytest.mark.parametrize(
    "hold_existing_final_probe", [False, True], ids=["normal", "existing-owned-closeout"]
)
def test_helper_and_client_share_creation_phases_and_real_stdlib_stop_proof(
    owner, payload, tmp_path, monkeypatch, hold_existing_final_probe
):
    import easyai.services.install_service as service_module
    import easyai.services.remote_install as target_module

    profiles = tmp_path / "profiles"
    profiles.mkdir()
    for path in PROFILE_ROOT.iterdir():
        if path.is_file():
            (profiles / path.name).write_bytes(path.read_bytes())
    data = json.loads((profiles / "easyai-cpu-sources.json").read_bytes())
    for item in data["packages"]:
        raw = ("SYNTHETIC-WHEEL-NOT-EXECUTABLE:" + item["name"]).encode()
        item["sha256"] = hashlib.sha256(raw).hexdigest()
        item["downloadBytes"] = len(raw)
        (Path(payload["configuration"]["wheelhouse"]) / item["filename"]).write_bytes(raw)
    (profiles / "easyai-cpu-sources.json").write_text(json.dumps(data))
    (profiles / "easyai-cpu-linux-cp311.lock").write_text(
        "".join(
            f"{w['name']}=={w['version']} --hash=sha256:{w['sha256']}\n" for w in data["packages"]
        )
    )
    monkeypatch.setattr(service_module, "PROFILE_ROOT", profiles)
    monkeypatch.setattr(target_module, "PROFILE_ROOT", profiles)
    identity = InstallTargetIdentity(**payload["identity"], root=payload["configuration"]["root"])
    config = RemoteConfiguration(
        **{
            k: v
            for k, v in payload["configuration"].items()
            if k not in {"root", "authorization_expires"}
        },
        authorization_expires=datetime.fromisoformat(
            payload["configuration"]["authorization_expires"]
        ),
        schema_version=1,
        conda_version="25.9.1",
        identity=identity,
    )
    app = tmp_path / "application"
    app.mkdir()
    attempts = []
    published, mark_ready_entered = threading.Event(), threading.Event()
    waiting, finish_owner = threading.Event(), threading.Event()
    held_phase, owner_threads, errors = [], [], []
    active_rpc = threading.local()
    original_publish, original_sleep = owner.publish_status, owner.time.sleep

    def publish(path, value):
        original_publish(path, value)
        if held_phase and str(path.parent) == held_phase[0]:
            published.set()  # Actual completed probe receipt, serve still owns writer FD.
            assert finish_owner.wait(3)

    def observe_wait(seconds):
        if getattr(active_rpc, "action", None) == "mark-ready":
            waiting.set()
        original_sleep(seconds)

    monkeypatch.setattr(owner, "publish_status", publish)
    monkeypatch.setattr(owner.time, "sleep", observe_wait)

    def rpc(request):
        if request["action"] != "run":
            active_rpc.action = request["action"]
            if request["action"] == "mark-ready" and not request["newEnvironment"]:
                mark_ready_entered.set()
            try:
                return owner.dispatch(request)
            except BaseException as error:
                errors.append((request["action"], str(error)))
                raise
            finally:
                active_rpc.action = None
        # Substitute ONLY in this fixture. No package/probe script can execute.
        original_source = request["argv"][-1]
        attempts.append(original_source)
        events = [dict(type="pipeline_completed", blockId=None, payload={})]
        if "report={" in original_source:
            tree = ast.parse(original_source)
            report = next(
                n
                for n in ast.walk(tree)
                if isinstance(n, ast.Assign)
                and any(isinstance(t, ast.Name) and t.id == "report" for t in n.targets)
            )
            nonce = ast.literal_eval(report.value.values[0])
            loops = [n for n in tree.body if isinstance(n, ast.For)]
            imports = ast.literal_eval(loops[1].iter)
            events.insert(
                0,
                dict(
                    type="progress",
                    blockId=None,
                    payload=dict(
                        nonce=nonce,
                        prefix=str(
                            Path(identity.root) / "training-environments" / request["environmentId"]
                        ),
                        pythonVersion="3.11.17",
                        versions={w["name"]: w["version"] for w in request["wheels"]},
                        imports={n: True for n in imports},
                        tensorOk=True,
                    ),
                ),
            )
        harmless = "\n".join(
            "print(" + repr("@@EASYAI_EVENT@@" + json.dumps(e)) + ",flush=True)" for e in events
        )
        safe = copy.deepcopy(request)
        safe["argv"] = [sys.executable, "-I", "-B", "-c", harmless]
        with monkeypatch.context() as patch:
            patch.setattr(
                owner.subprocess, "Popen", lambda *a, **k: None
            )  # Capture detach; no ACK races.
            receipt = owner.dispatch(safe)
        if (
            hold_existing_final_probe
            and not request["newEnvironment"]
            and "report={" in original_source
        ):
            held_phase.append(receipt["phaseRoot"])

            def serve():
                try:
                    owner.serve(receipt["phaseRoot"])
                except BaseException as error:
                    errors.append(("serve", str(error)))

            thread = threading.Thread(target=serve)
            owner_threads.append(thread)
            thread.start()
            assert published.wait(2)
        else:
            owner.serve(receipt["phaseRoot"])  # Real ManagedProcess for stdlib printer only.
        return owner.dispatch(
            {
                **{
                    k: v
                    for k, v in request.items()
                    if k not in {"argv", "environment", "helpers", "helperSource", "files"}
                },
                "action": "inspect",
            }
        )

    target = RemoteInstallTarget(
        app, config, SessionControl(project_id=identity.project_id, connection_id=str(uuid4())), rpc
    )
    service = InstallService(app, inspector=target.inspector, runtime=target, target=target)
    plan = service.plan(
        InstallPlanRequest(
            target_id=identity.target_id,
            remote_session=target.session,
            profile_id="easyai-cpu",
            package_ids=["torch"],
            new_environment_spec={"name": "synthetic"},
        )
    )
    job = service.confirm(
        InstallConfirmation(
            plan_id=plan.plan_id,
            plan_hash=plan.plan_hash,
            confirmed=True,
            network_acknowledged=True,
        )
    )
    service._workers[job.job_id].join(5)
    result = service.get(job.job_id)
    assert result.state == "SUCCEEDED", result.model_dump()
    assert result.verified and not result.needs_reprobe and not service._leases
    assert len(attempts) == 4 and any("--no-index" in s for s in attempts)
    target.bind(plan, job.job_id)
    target._local.new = False
    snapshot = target.call("snapshot")
    assert snapshot["ready"] and snapshot["owned"]
    existing_plan = service.plan(
        InstallPlanRequest(
            target_id=identity.target_id,
            remote_session=target.session,
            profile_id="easyai-cpu",
            package_ids=["torch"],
            owned_environment_id=plan.environment_id,
        )
    )
    second = service.confirm(
        InstallConfirmation(
            plan_id=existing_plan.plan_id,
            plan_hash=existing_plan.plan_hash,
            confirmed=True,
            network_acknowledged=True,
        )
    )
    if hold_existing_final_probe:
        try:
            assert published.wait(2) and mark_ready_entered.wait(2)
            observed_wait = waiting.wait(1)
        finally:
            finish_owner.set()
            for thread in owner_threads:
                thread.join(3)
    service._workers[second.job_id].join(5)
    if hold_existing_final_probe:
        assert observed_wait, f"mark-ready failed to await actual writer close: {errors}"
        assert all(not thread.is_alive() for thread in owner_threads)
    assert not errors
    result = service.get(second.job_id)
    assert result.state == "SUCCEEDED", result.model_dump()
    assert result.verified and not result.needs_reprobe and not service._leases
    assert len(attempts) == 6  # Existing owned target reuses install + actual probe adapter.
    target.bind(existing_plan, second.job_id)
    assert target.call("snapshot")["ready"]
    service.close()
