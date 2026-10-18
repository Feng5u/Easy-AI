import { test } from "node:test";
import assert from "node:assert/strict";
import { createRequire } from "node:module";
import {
  mkdtemp,
  mkdir,
  writeFile,
  rm,
  readFile,
  chmod,
  lstat,
} from "node:fs/promises";
import { join, dirname } from "node:path";
import { tmpdir } from "node:os";
import { verifyBuilder } from "./package-builder.mjs";
import { treeRecords } from "./package-inputs.mjs";
import { OFFLINE_DOCS, hash } from "./package.mjs";
const req = createRequire(import.meta.url);
const builder = createRequire(req.resolve("electron-builder"));
const asar = createRequire(builder.resolve("app-builder-lib"))(
  "@electron/asar",
);
async function fixture(t, extra) {
  const root = await mkdtemp(join(tmpdir(), "easyai-builder-verifier-"));
  t.after(() => rm(root, { recursive: true, force: true }));
  const app = join(root, "app-input");
  const files = [
    "linux-unpacked/easyai",
    "linux-unpacked/LICENSE",
    "linux-unpacked/LICENSE.electron.txt",
    "linux-unpacked/LICENSES.chromium.html",
    "linux-unpacked/resources/app.asar",
    "linux-unpacked/resources/backend/easyai-sidecar",
    "linux-unpacked/resources/notices/NOTICE.txt",
    "linux-unpacked/resources/notices/inventory.json",
    ...OFFLINE_DOCS.map((x) => `linux-unpacked/resources/offline/docs/${x}`),
    "fixture.tar.gz",
  ].sort();
  for (const file of files) {
    await mkdir(dirname(join(root, "artifacts", file)), { recursive: true });
    await writeFile(join(root, "artifacts", file), "fixture");
    await chmod(join(root, "artifacts", file), 0o644);
  }
  for (const [name, content] of Object.entries({
    "package.json": JSON.stringify({
      version: "0.0.0",
      type: "module",
      main: "dist-electron/main.mjs",
    }),
    "dist/index.html": "fixture",
    "dist-electron/main.mjs": "fixture",
    "dist-electron/preload.cjs": "fixture",
    ...(extra || {}),
  })) {
    await mkdir(dirname(join(app, name)), { recursive: true });
    await writeFile(join(app, name), content);
  }
  await asar.createPackage(
    app,
    join(root, "artifacts/linux-unpacked/resources/app.asar"),
  );
  const records = [];
  for (const file of files)
    records.push({
      path: file,
      bytes: (await readFile(join(root, "artifacts", file))).length,
      mode: (await lstat(join(root, "artifacts", file))).mode & 0o777,
      sha256: await hash(join(root, "artifacts", file)),
    });
  const base = join(root, "artifacts/linux-unpacked");
  const vendor = (await treeRecords(base))
    .filter(
      (r) =>
        !r.path.startsWith("resources/") && r.path !== "LICENSE.electron.txt",
    )
    .map((r) => ({ ...r, path: r.path === "easyai" ? "electron" : r.path }));
  const manifest = {
    schemaVersion: 2,
    kind: "unsigned-electron-builder-local",
    sourceCommit: "a".repeat(40),
    builderVersion: "26.15.3",
    version: "0.0.0",
    platform: "linux",
    arch: "x64",
    distributionReady: false,
    legalReviewComplete: false,
    approvedInputs: {
      schemaVersion: 1,
      origin: "exclusive-clean-build",
      sourceCommit: "a".repeat(40),
      appMetadata: JSON.stringify(
        JSON.parse(await readFile(join(app, "package.json"), "utf8")),
      ),
      groups: {
        app: await treeRecords(app),
        backend: await treeRecords(join(base, "resources/backend")),
        offline: await treeRecords(join(base, "resources/offline")),
        notices: await treeRecords(join(base, "resources/notices")),
        vendor,
      },
    },
    records,
  };
  const save = () =>
    writeFile(join(root, "builder-manifest.json"), JSON.stringify(manifest));
  await save();
  return { root, manifest, save };
}
test("builder verification detects modified and unrecorded payloads", async (t) => {
  const { root } = await fixture(t);
  assert.equal((await verifyBuilder(root)).distributionReady, false);
  const extra = join(root, "artifacts/private-machine.json");
  await writeFile(extra, "synthetic-private");
  await assert.rejects(verifyBuilder(root), /BUILDER_CONTENT_MISMATCH/);
  await rm(extra);
  await writeFile(
    join(root, "artifacts/linux-unpacked/resources/backend/easyai-sidecar"),
    "changed",
  );
  await assert.rejects(verifyBuilder(root), /BUILDER_CONTENT_MISMATCH/);
});
test("builder verifier refuses release claims and traversal before reading content", async (t) => {
  const { root, manifest, save } = await fixture(t);
  manifest.legalReviewComplete = true;
  await save();
  await assert.rejects(verifyBuilder(root), /BUILDER_MANIFEST_INVALID/);
  manifest.legalReviewComplete = false;
  manifest.records[0].path = "../private";
  await save();
  await assert.rejects(verifyBuilder(root), /BUILDER_MANIFEST_PATH_INVALID/);
});
test("builder verifier rejects development inputs inside an otherwise hashed ASAR", async (t) => {
  const { root } = await fixture(t, {
    "src/private.ts": "synthetic forbidden input",
  });
  await assert.rejects(verifyBuilder(root), /BUILDER_ASAR_UNEXPECTED_INPUT/);
});
test("builder verifier rejects private environment files even when hashes match", async (t) => {
  const { root } = await fixture(t, {
    "dist/.env.local": "SYNTHETIC_SECRET_ONLY",
  });
  await assert.rejects(verifyBuilder(root), /BUILDER_ASAR_UNEXPECTED_INPUT/);
});

test("output inventory cannot approve an extra resource with an ordinary name", async (t) => {
  const { root, manifest, save } = await fixture(t);
  const file = join(
    root,
    "artifacts/linux-unpacked/resources/offline/additional-reading.json",
  );
  await writeFile(file, "SYNTHETIC_UNREGISTERED_CONTENT");
  manifest.records = await treeRecords(join(root, "artifacts"));
  await save();
  await assert.rejects(
    verifyBuilder(root),
    /BUILDER_UNAPPROVED_RESOURCE: offline/,
  );
});
