// Real packaged sidecar, launched outside the checkout. No training or Electron window.
import { spawn } from "node:child_process";
import { randomBytes } from "node:crypto";
import { mkdtemp, mkdir, readFile, rm } from "node:fs/promises";
import { join, resolve } from "node:path";
import { tmpdir } from "node:os";
import { createInterface } from "node:readline";
import assert from "node:assert/strict";

const repository = resolve(import.meta.dirname, "..");
const build = join(repository, "services/backend/dist/easyai-sidecar");
const resources = join(build, "_internal/easyai/resources");
for (const name of ["entry.py", "easyai_runtime.py"])
  assert.deepEqual(
    await readFile(join(resources, "runtime", name)),
    await readFile(join(repository, "runtime", name)),
  );
assert.deepEqual(
  await readFile(join(resources, "templates/project.easyai.json")),
  await readFile(join(repository, "examples/mnist-cnn/project.easyai.json")),
);
assert.deepEqual(
  await readFile(join(resources, "templates/blank.json")),
  await readFile(join(repository, "packages/contracts/fixtures/blank.json")),
);
const root = await mkdtemp(join(tmpdir(), "easyai-frozen-"));
const project = join(root, "原生选择 项目");
await mkdir(project);
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
    (await request("GET", "/local/session", undefined, false)).response.status,
    401,
  );
  assert.equal(
    (await request("POST", "/local/preflight", {}, false)).response.status,
    401,
  );
  assert.equal(
    (await request("POST", "/local/preflight", { pythonPath: "/arbitrary" }))
      .response.status,
    422,
  );
  const profileInput = {
    alias: "冻结概要",
    endpoint: { host: "SYNTHETIC.invalid.", port: 22 },
    username: "student",
  };
  const rejectedProfile = await request("POST", "/connections", {
    ...profileInput,
    password: "synthetic-must-not-echo",
  });
  assert.equal(rejectedProfile.response.status, 422);
  assert.equal(
    JSON.stringify(rejectedProfile.value).includes("synthetic-must-not-echo"),
    false,
  );
  const savedProfile = await request("POST", "/connections", profileInput);
  assert.equal(savedProfile.response.status, 201);
  assert.equal(savedProfile.value.endpoint.host, "synthetic.invalid");
  const profileUpdate = {
    ...profileInput,
    alias: "新名称",
    expectedRevision: 1,
  };
  const updatedProfile = await request(
    "PATCH",
    `/connections/${savedProfile.value.targetId}`,
    profileUpdate,
  );
  assert.equal(updatedProfile.response.status, 200);
  assert.equal(updatedProfile.value.targetId, savedProfile.value.targetId);
  assert.equal(updatedProfile.value.revision, 2);
  assert.equal(
    (
      await request(
        "PATCH",
        `/connections/${savedProfile.value.targetId}`,
        profileUpdate,
      )
    ).response.status,
    412,
  );
  assert.deepEqual((await request("GET", "/connections")).value, [
    updatedProfile.value,
  ]);
  const selected = await request("POST", "/local/selections", {
    kind: "project",
    path: project,
  });
  assert.equal(selected.response.status, 200);
  const opened = await request("POST", "/projects", {
    selectionId: selected.value.selectionId,
    name: "冻结示例",
    template: "mnist-cnn",
  });
  assert.equal(opened.response.status, 200);
  const compiled = await request(
    "POST",
    `/projects/${opened.value.project.projectId}/compile`,
    { project: opened.value.project, requestId: 17 },
  );
  assert.equal(compiled.response.status, 200);
  assert.equal(compiled.value.runnable, true);
  assert.equal(
    compiled.value.code,
    await readFile(
      join(repository, "services/backend/tests/fixtures/golden/mnist.py.txt"),
      "utf8",
    ),
  );
  const blankDirectory = join(root, "blank project");
  await mkdir(blankDirectory);
  const blankSelection = await request("POST", "/local/selections", {
    kind: "project",
    path: blankDirectory,
  });
  const blank = await request("POST", "/projects", {
    selectionId: blankSelection.value.selectionId,
    name: "空白",
    template: "blank",
  });
  assert.equal(blank.response.status, 200);
  assert.deepEqual(blank.value.project.workspaces.data.blocks.blocks, []);
  const portable = join(root, "portable.easyai.json");
  assert.equal(
    (await request("POST", "/local/export", { path: portable })).response
      .status,
    200,
  );
  assert.deepEqual(
    await readFile(portable),
    await readFile(join(blankDirectory, "project.easyai.json")),
  );
  console.log(
    "PASS frozen resources + native-selection API + project create + authenticated golden compile from temporary cwd",
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
