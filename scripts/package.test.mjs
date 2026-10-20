import { test as nodeTest } from "node:test";
import assert from "node:assert/strict";
import {
  mkdtemp,
  mkdir,
  writeFile,
  readFile,
  rm,
  symlink,
  access,
  chmod,
} from "node:fs/promises";
import { join, dirname } from "node:path";
import { tmpdir } from "node:os";
import {
  stagePortable,
  verifyPortable,
  resourcePairs,
  OFFLINE_DOCS,
} from "./package.mjs";
const test = (name, run) =>
  nodeTest(
    name,
    { skip: process.platform !== "linux" || process.arch !== "x64" },
    run,
  );

async function fixture(t) {
  const base = await mkdtemp(join(tmpdir(), "easyai-package-fixture-"));
  t.after(() => rm(base, { recursive: true, force: true }));
  const root = join(base, "repository"),
    electronDist = join(base, "vendor"),
    output = join(base, "result");
  async function put(path, value = "fixture\n") {
    await mkdir(dirname(path), { recursive: true });
    await writeFile(path, value);
  }
  const backend = join(root, "services/backend/dist/easyai-sidecar");
  for (const [source, target] of resourcePairs) {
    await put(join(root, source), `fixture:${source}`);
    await put(
      join(backend, "_internal/easyai/resources", target),
      `fixture:${source}`,
    );
  }
  await put(
    join(root, "apps/desktop/package.json"),
    JSON.stringify({
      version: "0.0.0",
      devDependencies: { electron: "44.9.0" },
    }),
  );
  for (const path of [
    "dist/index.html",
    "dist/assets/offline.js",
    "dist-electron/main.mjs",
    "dist-electron/preload.cjs",
  ])
    await put(join(root, "apps/desktop", path));
  for (const name of OFFLINE_DOCS) await put(join(root, "docs", name));
  await put(join(root, "tutorials/zh-CN/fixture.md"));
  await put(join(root, "private-token.txt"), "NEVER PACKAGE");
  const header = Buffer.alloc(20);
  header.set([127, 69, 76, 70, 2, 1]);
  header.writeUInt16LE(62, 18);
  await put(join(electronDist, "electron"), header);
  await chmod(join(electronDist, "electron"), 0o755);
  await put(join(electronDist, "version"), "44.9.0\n");
  await put(join(electronDist, "LICENSE"));
  await put(join(electronDist, "LICENSES.chromium.html"));
  await mkdir(join(electronDist, "resources"));
  await put(join(backend, "easyai-sidecar"), header);
  await chmod(join(backend, "easyai-sidecar"), 0o755);
  async function notices(_root, target) {
    await mkdir(target);
    await put(join(target, "NOTICE.txt"));
    await put(join(target, "inventory.json"), "{}");
  }
  return { root, electronDist, output, notices, backend, put };
}
test("offline allowlist stages manifest, resources, docs and notices without private checkout files", async (t) => {
  const options = await fixture(t);
  const result = await stagePortable(options);
  assert.equal(result.distributionReady, false);
  const manifest = JSON.parse(
    await readFile(join(options.output, "package-manifest.json")),
  );
  assert.equal(manifest.launch, "easyai");
  assert.ok(manifest.records.some((x) => x.path === "easyai"));
  await assert.rejects(access(join(options.output, "electron")));
  // The cached vendor input is untouched. Electron 44 marks the basename
  // 'electron' as development; the branded copied entry must be different.
  await access(join(options.electronDist, "electron"));
  assert.ok(
    manifest.records.some(
      (x) =>
        x.path ===
        "resources/backend/_internal/easyai/resources/templates/project.easyai.json",
    ),
  );
  assert.ok(
    !manifest.records.some((x) =>
      /private-token|\.venv|machine\.local|\/runs\//.test(x.path),
    ),
  );
  assert.deepEqual(await verifyPortable(options.output), result);
});
test("refuses existing destination and preserves another writer's contents", async (t) => {
  const options = await fixture(t);
  await mkdir(options.output);
  await options.put(join(options.output, "keep.txt"), "other writer");
  await assert.rejects(stagePortable(options), { code: "EEXIST" });
  assert.equal(
    await readFile(join(options.output, "keep.txt"), "utf8"),
    "other writer",
  );
});
test("stale frozen source fails before creating output", async (t) => {
  const options = await fixture(t);
  await writeFile(
    join(options.backend, "_internal/easyai/resources/manifest.json"),
    "stale",
  );
  await assert.rejects(stagePortable(options), /PACKAGE_STALE_RESOURCE/);
  await assert.rejects(access(options.output));
});
test("symlink in source is refused and failed output has no completion manifest", async (t) => {
  const options = await fixture(t);
  await symlink(
    join(options.root, "private-token.txt"),
    join(options.root, "apps/desktop/dist/assets/unsafe"),
  );
  await assert.rejects(stagePortable(options), /PACKAGE_SYMLINK_FORBIDDEN/);
  await assert.rejects(access(join(options.output, "package-manifest.json")));
});
test("verification rejects tampering, extra files and manifest traversal", async (t) => {
  const options = await fixture(t);
  await stagePortable(options);
  const file = join(options.output, "resources/offline/docs/teacher-setup.md");
  const original = await readFile(file);
  await writeFile(file, "changed");
  await assert.rejects(
    verifyPortable(options.output),
    /PACKAGE_CONTENT_MISMATCH/,
  );
  await writeFile(file, original);
  const extra = join(options.output, "unexpected.txt");
  await writeFile(extra, "extra");
  await assert.rejects(
    verifyPortable(options.output),
    /PACKAGE_UNRECORDED_CONTENT/,
  );
  await rm(extra);
  const path = join(options.output, "package-manifest.json"),
    manifest = JSON.parse(await readFile(path));
  manifest.records[0].path = "../outside";
  await writeFile(path, JSON.stringify(manifest));
  await assert.rejects(
    verifyPortable(options.output),
    /PACKAGE_MANIFEST_PATH_INVALID/,
  );
});
test("wrong Electron version or native architecture is rejected before output", async (t) => {
  const options = await fixture(t);
  await writeFile(join(options.electronDist, "version"), "different");
  await assert.rejects(
    stagePortable(options),
    /PACKAGE_ELECTRON_VERSION_MISMATCH/,
  );
  await writeFile(join(options.electronDist, "version"), "44.9.0");
  const path = join(options.backend, "easyai-sidecar"),
    value = await readFile(path);
  value.writeUInt16LE(183, 18);
  await writeFile(path, value);
  await assert.rejects(
    stagePortable(options),
    /PACKAGE_NATIVE_PLATFORM_MISMATCH/,
  );
  await assert.rejects(access(options.output));
});
