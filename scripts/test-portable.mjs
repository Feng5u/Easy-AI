// Verify the actual copied frozen executable with Main's packaged launch code.
// Does not launch Electron (the existing sandbox denial is not retried).
import { mkdtemp, mkdir, readFile, rm } from "node:fs/promises";
import { join, resolve } from "node:path";
import { tmpdir } from "node:os";
import assert from "node:assert/strict";
import { verifyPortable, defaultOutput } from "./package.mjs";
const repository = resolve(import.meta.dirname, "..");
const output = defaultOutput(repository);
await verifyPortable(output);
const manifest = JSON.parse(
  await readFile(join(output, "package-manifest.json"), "utf8"),
);
assert.equal(manifest.launch, "easyai");
assert.notEqual(manifest.launch.toLowerCase(), "electron");
const { backendLocation } = await import(
  join(output, "resources/app/dist-electron/backend-location.mjs")
);
const { startBackend } = await import(
  join(output, "resources/app/dist-electron/backend.mjs")
);
const root = await mkdtemp(join(tmpdir(), "easyai-portable-smoke-"));
let backend;
try {
  const launch = backendLocation(
    true,
    join(output, "resources"),
    join(root, "NONEXISTENT-CHECKOUT"),
    process.platform,
  );
  assert.deepEqual(launch.args, []);
  backend = await startBackend(
    launch.executable,
    launch.cwd,
    15000,
    join(root, "state"),
    launch.args,
  );
  const project = join(root, "independent project");
  await mkdir(project);
  const selection = await backend.request("POST", "/api/v1/local/selections", {
    kind: "project",
    path: project,
  });
  const opened = await backend.request("POST", "/api/v1/projects", {
    selectionId: selection.selectionId,
    name: "portable fixture",
    template: "mnist-cnn",
  });
  const compiled = await backend.request(
    "POST",
    `/api/v1/projects/${opened.project.projectId}/compile`,
    { project: opened.project, requestId: 1 },
  );
  assert.equal(compiled.runnable, true);
  assert.equal(
    compiled.code,
    await readFile(
      join(repository, "services/backend/tests/fixtures/golden/mnist.py.txt"),
      "utf8",
    ),
  );
  const catalog = await backend.request("GET", "/api/v1/catalog/packages");
  assert.equal(catalog.executionEnabled, false);
  await backend.stop();
  assert.equal(backend.process.exitCode, 0);
  console.log(
    "PASS actual portable resources + Main frozen launch + independent state/project + authenticated golden compile + EOF0; no Electron window/training/SSH",
  );
} finally {
  try {
    if (backend) await backend.stop();
  } finally {
    await rm(root, { recursive: true, force: true });
  }
}
