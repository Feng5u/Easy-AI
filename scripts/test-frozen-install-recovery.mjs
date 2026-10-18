// Real packaged process restart. No installer, dependency network or environment creation.
import { spawn } from "node:child_process";
import { randomBytes } from "node:crypto";
import { mkdtemp, rm, access } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join, resolve } from "node:path";
import { createInterface } from "node:readline";
import assert from "node:assert/strict";

const root = await mkdtemp(join(tmpdir(), "easyai-install-restart-"));
const binary = resolve(
  import.meta.dirname,
  "../services/backend/dist/easyai-sidecar",
  process.platform === "win32" ? "easyai-sidecar.exe" : "easyai-sidecar",
);
async function launch() {
  const token = randomBytes(32).toString("hex");
  const child = spawn(binary, [], { cwd: root, shell: false, stdio: "pipe" });
  child.stderr.resume();
  child.stdin.on("error", () => {});
  const exited = new Promise((yes, no) => {
    child.once("exit", yes);
    child.once("error", no);
  });
  void exited.catch(() => {});
  const lines = createInterface({ input: child.stdout });
  const stop = async () => {
    child.stdin.end();
    const timer = setTimeout(() => child.kill("SIGKILL"), 10000);
    try {
      await exited;
      assert.equal(child.exitCode, 0);
    } finally {
      clearTimeout(timer);
      lines.close();
    }
  };
  try {
    const ready = await new Promise((yes, no) => {
      const timer = setTimeout(() => no(new Error("startup timeout")), 15000);
      lines.once("line", (line) => {
        clearTimeout(timer);
        try {
          yes(JSON.parse(line));
        } catch (error) {
          no(error);
        }
      });
      child.once("error", (error) => {
        clearTimeout(timer);
        no(error);
      });
      child.stdin.write(
        JSON.stringify({ token, storageRoot: join(root, "state") }) + "\n",
      );
    });
    return {
      stop,
      async request(method, path, body) {
        const response = await fetch(
          `http://127.0.0.1:${ready.port}/api/v1${path}`,
          {
            method,
            headers: {
              Authorization: `Bearer ${token}`,
              "Content-Type": "application/json",
            },
            ...(body ? { body: JSON.stringify(body) } : {}),
            signal: AbortSignal.timeout(10000),
            redirect: "error",
          },
        );
        return { status: response.status, value: await response.json() };
      },
    };
  } catch (error) {
    await stop();
    throw error;
  }
}
let active;
try {
  active = await launch();
  const plan = await active.request("POST", "/environments/install-plan", {
    targetId: "local",
    profileId: "easyai-cpu",
    packageIds: ["torch"],
    newEnvironmentSpec: { name: "restart_fixture" },
  });
  assert.equal(plan.status, 200);
  const confirmed = await active.request("POST", "/install-jobs", {
    planId: plan.value.planId,
    planHash: plan.value.planHash,
    confirmed: true,
    networkAcknowledged: true,
  });
  if (process.platform === "linux" && process.arch === "x64") {
    assert.equal(confirmed.status, 202);
    assert.equal(confirmed.value.state, "AWAITING_EXECUTION");
    const id = confirmed.value.jobId;
    await active.stop();
    active = undefined;
    active = await launch();
    const recovered = await active.request("GET", `/install-jobs/${id}`);
    assert.equal(recovered.status, 200);
    assert.equal(recovered.value.state, "CANCELLED");
    assert.equal(
      recovered.value.statusCode,
      "INSTALL_RESTART_CONFIRMATION_EXPIRED",
    );
    assert.equal(recovered.value.verified, false);
    assert.equal(recovered.value.executionEnabled, false);
    assert.equal(recovered.value.changesPossible, false);
    assert.equal(
      (await active.request("POST", `/install-jobs/${id}/cancel`)).value.state,
      "CANCELLED",
    );
    await assert.rejects(access(join(root, "state/training-environments")));
    console.log(
      "PASS frozen real process restart + durable job lookup + expired confirmation; no environment or installer",
    );
  } else {
    assert.equal(confirmed.status, 409);
    console.log(
      "PASS frozen unsupported profile refuses confirmation; restart install test NOT RUN on this platform",
    );
  }
} finally {
  try {
    if (active) await active.stop();
  } finally {
    await rm(root, { recursive: true, force: true });
  }
}
