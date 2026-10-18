// Frozen M5 identity API from temporary cwd. No outbound SSH, credentials or training.
import { spawn } from "node:child_process";
import { randomBytes } from "node:crypto";
import { mkdtemp, rm } from "node:fs/promises";
import { join, resolve } from "node:path";
import { tmpdir } from "node:os";
import { createInterface } from "node:readline";
import assert from "node:assert/strict";

const repository = resolve(import.meta.dirname, "..");
const build = join(repository, "services/backend/dist/easyai-sidecar");
const root = await mkdtemp(join(tmpdir(), "easyai-frozen-ssh-"));
const token = randomBytes(32).toString("hex");
const child = spawn(
  join(
    build,
    process.platform === "win32" ? "easyai-sidecar.exe" : "easyai-sidecar",
  ),
  [],
  { cwd: root, stdio: "pipe", shell: false },
);
child.stderr.resume();
child.stdin.on("error", () => {});
const exited = new Promise((resolveExit, reject) => {
  child.once("exit", resolveExit);
  child.once("error", reject);
});
void exited.catch(() => undefined);
const lines = createInterface({ input: child.stdout });
try {
  const ready = await new Promise((resolveReady, reject) => {
    const timer = setTimeout(
      () => reject(new Error("frozen startup timeout")),
      15000,
    );
    lines.once("line", (line) => {
      clearTimeout(timer);
      try {
        resolveReady(JSON.parse(line));
      } catch (error) {
        reject(error);
      }
    });
    child.once("error", (error) => {
      clearTimeout(timer);
      reject(error);
    });
    child.stdin.write(
      JSON.stringify({ token, storageRoot: join(root, "state") }) + "\n",
    );
  });
  assert.equal(ready.protocolVersion, 1);
  async function request(method, path, body, authorized = true) {
    const response = await fetch(
      `http://127.0.0.1:${ready.port}/api/v1${path}`,
      {
        method,
        headers: {
          ...(authorized ? { Authorization: `Bearer ${token}` } : {}),
          "Content-Type": "application/json",
        },
        ...(body ? { body: JSON.stringify(body) } : {}),
        signal: AbortSignal.timeout(10000),
        redirect: "error",
      },
    );
    return { response, value: await response.json() };
  }
  assert.equal(
    (
      await request(
        "POST",
        "/connections/probe",
        { host: "offline.invalid" },
        false,
      )
    ).response.status,
    401,
  );
  assert.equal(
    (await request("POST", "/connections/probe", { host: "invalid/host" }))
      .response.status,
    422,
  );
  const rejected = await request("POST", "/connections/probe", {
    host: "offline.invalid",
    password: "DO_NOT_ECHO_TEST_MARKER",
  });
  assert.equal(rejected.response.status, 422);
  assert.equal(JSON.stringify(rejected.value).includes("DO_NOT_ECHO"), false);
  // This path lazily imports packaged Paramiko without dialing any SSH endpoint.
  const expired = await request("POST", "/connections/trust-host-key", {
    challengeId: "00000000-0000-0000-0000-000000000000",
    fingerprint: "SHA256:" + "A".repeat(43),
  });
  assert.equal(expired.response.status, 422);
  assert.equal(expired.value.error.code, "SSH_CONFIRMATION_EXPIRED");
  const scoped = {
    projectId: "11111111-1111-4111-8111-111111111111",
    requestId: "22222222-2222-4222-8222-222222222222",
  };
  const cancelled = await request(
    "POST",
    "/connections/identity/cancel",
    scoped,
  );
  assert.equal(cancelled.response.status, 200);
  assert.equal(cancelled.value.cancelled, true);
  const invalidScope = await request("POST", "/connections/identity/confirm", {
    ...scoped,
    confirmation: {
      challengeId: "00000000-0000-0000-0000-000000000000",
      fingerprint: "SHA256:" + "A".repeat(43),
    },
  });
  assert.equal(invalidScope.response.status, 422);
  assert.equal(invalidScope.value.error.code, "SSH_IDENTITY_PROJECT_CHANGED");
  console.log(
    "PASS frozen SSH routes + auth + strict DTO + sanitized errors + scoped cancel/confirm + lazy Paramiko; no outbound SSH",
  );
} finally {
  child.stdin.end();
  const timer = setTimeout(() => child.kill("SIGKILL"), 20000);
  try {
    await exited;
  } finally {
    clearTimeout(timer);
    lines.close();
    await rm(root, { recursive: true, force: true });
  }
}
assert.equal(child.exitCode, 0);
console.log("PASS frozen sidecar EOF exit 0");
