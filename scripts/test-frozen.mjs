// Real packaged sidecar, launched outside the checkout. No training or Electron window.
import { spawn } from "node:child_process";
import { randomBytes, createHash } from "node:crypto";
import { mkdtemp, mkdir, readFile, writeFile, rm } from "node:fs/promises";
import { join, resolve } from "node:path";
import { tmpdir } from "node:os";
import { createInterface } from "node:readline";
import assert from "node:assert/strict";

import {
  safeRequest,
  readSmokeResponse,
  stderrDiagnostics,
} from "./frozen-diagnostics.mjs";

const repository = resolve(import.meta.dirname, "..");
if (process.argv.length > 3)
  throw Error("Usage: node scripts/test-frozen.mjs [backend-directory]");
const build = process.argv[2]
  ? resolve(process.argv[2])
  : join(repository, "services/backend/dist/easyai-sidecar");
const resources = join(build, "_internal/easyai/resources");
for (const name of ["entry.py", "easyai_runtime.py", "install_owner.py"])
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
const stderr = stderrDiagnostics();
child.stderr.on("data", (chunk) => stderr.append(chunk));
const closed = new Promise((resolveClose) => child.once("close", resolveClose));
let lastRequest = null;
let failed = false;
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
  assert.deepEqual(Object.keys(ready).sort(), [
    "pid",
    "port",
    "protocolVersion",
  ]);
  assert.equal(ready.pid, child.pid);
  assert.equal(
    Number.isInteger(ready.port) && ready.port >= 1 && ready.port <= 65535,
    true,
  );
  assert.equal(ready.protocolVersion, 1);
  async function request(method, path, body, authorized = true) {
    lastRequest = safeRequest(method, path);
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
    lastRequest = safeRequest(method, path, response.status);
    return readSmokeResponse(response, lastRequest);
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
  const packages = await request("GET", "/catalog/packages");
  assert.equal(packages.response.status, 200);
  assert.equal(packages.value.executionEnabled, false);
  assert.equal(packages.value.packages.length, 17);
  const invalidSource = join(root, "synthetic-invalid-source.json");
  await writeFile(invalidSource, "{}", { mode: 0o600, flag: "wx" });
  const sourceBody = { manifestPath: invalidSource, packageIds: ["torch"] };
  assert.equal(
    (
      await request(
        "POST",
        "/environments/install-source/preview",
        sourceBody,
        false,
      )
    ).response.status,
    401,
  );
  const rejectedSource = await request(
    "POST",
    "/environments/install-source/preview",
    sourceBody,
  );
  assert.equal(rejectedSource.response.status, 422);
  assert.equal(
    JSON.stringify(rejectedSource.value).includes(invalidSource),
    false,
  );
  await assert.rejects(readFile(join(root, "state/install-runtime.json")), {
    code: "ENOENT",
  });
  const expectedSources = await readFile(
    join(repository, "packages/training-profiles/easyai-cpu-sources.json"),
  );
  const expectedLock = await readFile(
    join(repository, "packages/training-profiles/easyai-cpu-linux-cp311.lock"),
  );
  const expectedMlSources = await readFile(
    join(repository, "packages/training-profiles/easyai-ml-sources.json"),
  );
  const expectedMlLock = await readFile(
    join(repository, "packages/training-profiles/easyai-ml-linux-cp311.lock"),
  );
  const expectedCvSources = await readFile(
    join(repository, "packages/training-profiles/easyai-cv-sources.json"),
  );
  const expectedCvLock = await readFile(
    join(repository, "packages/training-profiles/easyai-cv-linux-cp311.lock"),
  );
  const expectedNlpSources = await readFile(
    join(repository, "packages/training-profiles/easyai-nlp-sources.json"),
  );
  const expectedNlpLock = await readFile(
    join(repository, "packages/training-profiles/easyai-nlp-linux-cp311.lock"),
  );
  for (const name of ["easyai-nlp-sources.json", "easyai-nlp-linux-cp311.lock"])
    assert.deepEqual(
      await readFile(join(resources, "training-profiles", name)),
      await readFile(join(repository, "packages/training-profiles", name)),
    );
  const expectedDlSources = await readFile(
    join(repository, "packages/training-profiles/easyai-dl-sources.json"),
  );
  const expectedDlLock = await readFile(
    join(repository, "packages/training-profiles/easyai-dl-linux-cp311.lock"),
  );
  assert.deepEqual(
    await readFile(join(resources, "training-profiles/easyai-dl-sources.json")),
    expectedDlSources,
  );
  assert.deepEqual(
    await readFile(
      join(resources, "training-profiles/easyai-dl-linux-cp311.lock"),
    ),
    expectedDlLock,
  );
  assert.deepEqual(
    await readFile(join(resources, "training-profiles/easyai-cv-sources.json")),
    expectedCvSources,
  );
  assert.deepEqual(
    await readFile(
      join(resources, "training-profiles/easyai-cv-linux-cp311.lock"),
    ),
    expectedCvLock,
  );
  assert.deepEqual(
    await readFile(join(resources, "training-profiles/easyai-ml-sources.json")),
    expectedMlSources,
  );
  assert.deepEqual(
    await readFile(
      join(resources, "training-profiles/easyai-ml-linux-cp311.lock"),
    ),
    expectedMlLock,
  );
  assert.deepEqual(
    await readFile(join(resources, "package-groups/catalog.json")),
    await readFile(join(repository, "packages/package-groups/catalog.json")),
  );
  assert.deepEqual(
    await readFile(
      join(resources, "training-profiles/easyai-cpu-sources.json"),
    ),
    expectedSources,
  );
  assert.deepEqual(
    await readFile(
      join(resources, "training-profiles/easyai-cpu-linux-cp311.lock"),
    ),
    expectedLock,
  );
  const planned = await request("POST", "/environments/install-plan", {
    targetId: "local",
    profileId: "easyai-cpu",
    packageIds: ["torch"],
    newEnvironmentSpec: { name: "frozen_classroom" },
  });
  assert.equal(planned.response.status, 200);
  assert.equal(
    planned.value.constraintsHash,
    createHash("sha256")
      .update(expectedSources)
      .update(expectedLock)
      .update(expectedMlSources)
      .update(expectedMlLock)
      .update(expectedCvSources)
      .update(expectedCvLock)
      .update(expectedDlSources)
      .update(expectedDlLock)
      .update(expectedNlpSources)
      .update(expectedNlpLock)
      .digest("hex"),
  );
  const ml = await request("POST", "/environments/install-plan", {
    targetId: "local",
    profileId: "easyai-cpu",
    packageIds: ["numpy", "scipy", "pandas", "matplotlib", "scikit-learn"],
    newEnvironmentSpec: { name: "frozen_ml" },
  });
  assert.equal(ml.response.status, 200);
  assert.equal(ml.value.executionEnabled, false);
  assert.equal(ml.value.installedBytes, null);
  if (process.platform === "linux" && process.arch === "x64") {
    assert.deepEqual(ml.value.blockers, []);
  }
  assert.equal(
    ml.value.packageChanges.find((c) => c.packageId === "scikit-learn")
      .targetVersion,
    "1.8.0",
  );
  const cv = await request("POST", "/environments/install-plan", {
    targetId: "local",
    profileId: "easyai-cpu",
    packageIds: ["scikit-image"],
    newEnvironmentSpec: { name: "frozen_cv" },
  });
  assert.equal(cv.response.status, 200);
  assert.equal(cv.value.executionEnabled, false);
  assert.equal(cv.value.installedBytes, null);
  if (process.platform === "linux" && process.arch === "x64") {
    assert.deepEqual(cv.value.blockers, []);
  }
  const dlPlans = [];
  for (const packageIds of [
    ["pytorch-lightning"],
    ["torch", "torchvision", "pytorch-lightning"],
  ]) {
    const dl = await request("POST", "/environments/install-plan", {
      targetId: "local",
      profileId: "easyai-cpu",
      packageIds,
      newEnvironmentSpec: { name: "frozen_dl" },
    });
    assert.equal(dl.response.status, 200);
    assert.equal(dl.value.executionEnabled, false);
    assert.equal(dl.value.installedBytes, null);
    assert.equal(
      dl.value.packageChanges.find((c) => c.packageId === "pytorch-lightning")
        .targetVersion,
      "2.6.6",
    );
    if (process.platform === "linux" && process.arch === "x64") {
      assert.deepEqual(dl.value.blockers, []);
      assert.equal(dl.value.packageChanges.length, 35);
      assert.equal(
        new Set(dl.value.packageChanges.map((c) => c.packageId)).size,
        35,
      );
      assert.equal(
        dl.value.packageChanges.find((c) => c.packageId === "torch")
          .targetVersion,
        "2.10.0+cpu",
      );
    }
    dlPlans.push(dl.value);
  }
  assert.equal(dlPlans[0].downloadBytes, dlPlans[1].downloadBytes);
  const nlp = await request("POST", "/environments/install-plan", {
    targetId: "local",
    profileId: "easyai-cpu",
    packageIds: ["sentencepiece"],
    newEnvironmentSpec: { name: "frozen_nlp" },
  });
  assert.equal(nlp.response.status, 200);
  assert.equal(nlp.value.executionEnabled, false);
  assert.equal(nlp.value.installedBytes, null);
  assert.equal(nlp.value.constraintsHash, planned.value.constraintsHash);
  assert.equal(
    nlp.value.packageChanges.find((c) => c.packageId === "sentencepiece")
      .targetVersion,
    "0.2.2",
  );
  if (process.platform === "linux" && process.arch === "x64") {
    assert.deepEqual(nlp.value.blockers, []);
    assert.equal(nlp.value.packageChanges.length, 22);
    assert.equal(
      nlp.value.downloadBytes,
      JSON.parse(expectedSources).packages.reduce(
        (sum, p) => sum + p.downloadBytes,
        0,
      ) + 1394242,
    );
  }
  const nlpMetadata = JSON.parse(expectedNlpSources);
  for (const [packageId, version, expectedCount] of [
    ["spacy", "3.8.16", 60],
    ["transformers", "5.20.1", 43],
    ["gensim", "4.4.0", 25],
  ]) {
    const candidate = await request("POST", "/environments/install-plan", {
      targetId: "local",
      profileId: "easyai-cpu",
      packageIds: [packageId],
      newEnvironmentSpec: { name: "frozen_nlp_default" },
    });
    assert.equal(candidate.response.status, 200);
    assert.equal(candidate.value.executionEnabled, false);
    assert.equal(candidate.value.installedBytes, null);
    assert.equal(
      candidate.value.packageChanges.find((c) => c.packageId === packageId)
        .targetVersion,
      version,
    );
    if (process.platform === "linux" && process.arch === "x64") {
      assert.deepEqual(candidate.value.blockers, []);
      assert.equal(candidate.value.packageChanges.length, expectedCount);
      assert.equal(
        candidate.value.downloadBytes,
        JSON.parse(expectedSources).packages.reduce(
          (sum, p) => sum + p.downloadBytes,
          0,
        ) + nlpMetadata.defaultClosures[packageId].addedToCoreBytes,
      );
    }
  }
  const rejectedNlp = await request("POST", "/environments/install-plan", {
    targetId: "local",
    profileId: "easyai-cpu",
    packageIds: [
      "nltk",
      "sentencepiece",
      "spacy",
      "transformers",
      "gensim",
      "hanlp",
    ],
    newEnvironmentSpec: { name: "frozen_nlp_group" },
  });
  assert.equal(rejectedNlp.response.status, 200);
  assert.equal(rejectedNlp.value.executionEnabled, false);
  assert.equal(rejectedNlp.value.downloadBytes, null);
  assert(
    rejectedNlp.value.blockers.includes("INSTALL_KNOWN_PACKAGE_VULNERABILITY"),
  );
  assert(
    rejectedNlp.value.blockers.includes("INSTALL_BINARY_WHEEL_UNAVAILABLE"),
  );
  const opencv = await request("POST", "/environments/install-plan", {
    targetId: "local",
    profileId: "easyai-cpu",
    packageIds: ["opencv-python"],
    newEnvironmentSpec: { name: "frozen_opencv" },
  });
  assert.equal(opencv.response.status, 200);
  assert.ok(
    opencv.value.blockers.includes("INSTALL_NATIVE_REQUIREMENTS_UNVERIFIED"),
  );
  assert.equal(opencv.value.downloadBytes, null);
  assert.equal(opencv.value.executionEnabled, false);
  const acknowledged = {
    planId: planned.value.planId,
    planHash: planned.value.planHash,
    confirmed: true,
    networkAcknowledged: true,
  };
  if (process.platform === "linux" && process.arch === "x64") {
    assert.deepEqual(planned.value.blockers, []);
    const pending = await request("POST", "/install-jobs", acknowledged);
    assert.equal(pending.response.status, 202);
    assert.equal(pending.value.state, "AWAITING_EXECUTION");
    assert.equal(pending.value.executionEnabled, false);
    const cancelled = await request(
      "POST",
      `/install-jobs/${pending.value.jobId}/cancel`,
    );
    assert.equal(cancelled.response.status, 200);
    assert.equal(cancelled.value.state, "CANCELLED");
    assert.equal(cancelled.value.verified, false);
  } else {
    assert.deepEqual(planned.value.blockers, [
      "INSTALL_PROFILE_PLATFORM_UNSUPPORTED",
    ]);
    assert.equal(
      (await request("POST", "/install-jobs", acknowledged)).response.status,
      409,
    );
  }
  console.log(
    "PASS frozen offline package plan + explicit registration/cancel; execution remains disabled",
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
} catch (error) {
  failed = true;
  throw error;
} finally {
  child.stdin.end();
  const timer = setTimeout(() => child.kill("SIGKILL"), 20000);
  try {
    await exited;
    await closed;
  } finally {
    if (failed || child.exitCode !== 0)
      console.error(
        "FROZEN_SMOKE_DIAGNOSTIC",
        JSON.stringify({ lastRequest, stderr: stderr.summary() }),
      );
    clearTimeout(timer);
    lines.close();
    await rm(root, { recursive: true, force: true });
  }
}
assert.equal(child.exitCode, 0);
console.log("PASS frozen sidecar EOF exit 0");
