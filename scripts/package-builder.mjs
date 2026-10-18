// Real electron-builder API. Same-host local unsigned artifacts only; never publish.
import { build, Platform, Arch } from "electron-builder";
import baseConfiguration from "../electron-builder.json" with { type: "json" };
import { createRequire } from "node:module";
import { createHash } from "node:crypto";
import {
  cleanBuildInputs,
  stageInputs,
  treeRecords,
  INPUT_GROUPS,
} from "./package-inputs.mjs";
import { execFileSync } from "node:child_process";
import { mkdir, readFile, writeFile, readdir, lstat } from "node:fs/promises";
import { join, resolve, isAbsolute } from "node:path";
import { fileURLToPath } from "node:url";
import { hash, resourcePairs, OFFLINE_DOCS } from "./package.mjs";

const repository = resolve(import.meta.dirname, "..");
const require = createRequire(import.meta.url);
const builderRequire = createRequire(require.resolve("electron-builder"));
const dependencyRequire = createRequire(
  builderRequire.resolve("app-builder-lib"),
);
const asar = dependencyRequire("@electron/asar");
const manifestName = "builder-manifest.json";
export function builderConfiguration(stage, output, electronDist, version) {
  return {
    ...baseConfiguration,
    electronVersion: version,
    electronDist,
    directories: { app: join(stage, "resources/app"), output },
    extraResources: ["backend", "offline", "notices"].map((name) => ({
      from: join(stage, "resources", name),
      to: name,
      filter: ["**/*", "!**/.env*", "!**/machine.local.json"],
    })),
    // Vendor licenses stay outside ASAR for inspection.
    extraFiles: ["LICENSE", "LICENSES.chromium.html"].map((name) => ({
      from: join(electronDist, name),
      to: name,
    })),
  };
}
async function inventory(root, prefix = "") {
  const result = [];
  for (const name of (await readdir(join(root, prefix))).sort()) {
    const relative = prefix ? `${prefix}/${name}` : name;
    const info = await lstat(join(root, relative));
    if (info.isSymbolicLink()) throw Error("BUILDER_SYMLINK_FORBIDDEN");
    if (info.isDirectory()) result.push(...(await inventory(root, relative)));
    else if (info.isFile())
      result.push({
        path: relative,
        bytes: info.size,
        mode: info.mode & 0o777,
        sha256: await hash(join(root, relative)),
      });
    else throw Error("BUILDER_SPECIAL_FILE_FORBIDDEN");
  }
  return result;
}
export async function verifyBuilder(output) {
  const manifest = JSON.parse(
    await readFile(join(output, manifestName), "utf8"),
  );
  if (
    manifest.schemaVersion !== 2 ||
    manifest.kind !== "unsigned-electron-builder-local" ||
    manifest.distributionReady !== false ||
    manifest.legalReviewComplete !== false ||
    manifest.builderVersion !== "26.15.3" ||
    manifest.platform !== "linux" ||
    manifest.arch !== "x64" ||
    !/^[0-9a-f]{40}$/.test(manifest.sourceCommit) ||
    !Array.isArray(manifest.records)
  )
    throw Error("BUILDER_MANIFEST_INVALID");
  for (const record of manifest.records) {
    if (
      typeof record.path !== "string" ||
      isAbsolute(record.path) ||
      record.path.includes("\\") ||
      record.path.split("/").some((x) => !x || x === "." || x === "..")
    )
      throw Error("BUILDER_MANIFEST_PATH_INVALID");
  }
  const actual = await inventory(join(output, "artifacts"));
  if (JSON.stringify(actual) !== JSON.stringify(manifest.records))
    throw Error("BUILDER_CONTENT_MISMATCH");
  const names = new Set(actual.map((r) => r.path));
  for (const name of [
    "linux-unpacked/easyai",
    "linux-unpacked/LICENSE",
    "linux-unpacked/LICENSES.chromium.html",
    "linux-unpacked/resources/app.asar",
    "linux-unpacked/resources/backend/easyai-sidecar",
    "linux-unpacked/resources/notices/NOTICE.txt",
    "linux-unpacked/resources/notices/inventory.json",
    ...OFFLINE_DOCS.map((x) => `linux-unpacked/resources/offline/docs/${x}`),
  ])
    if (!names.has(name)) throw Error(`BUILDER_RESOURCE_MISSING: ${name}`);
  const archives = actual.filter((r) => r.path.endsWith(".tar.gz"));
  if (archives.length !== 1) throw Error("BUILDER_ARCHIVE_MISSING");
  const archive = join(output, "artifacts/linux-unpacked/resources/app.asar");
  const entries = asar.listPackage(archive);
  if (
    entries.some((name) =>
      /(?:^|\/)(?:node_modules|src|\.env[^/]*|\.git|machine\.local\.json)(?:\/|$)|\.map$|\.test\.[^/]+$/.test(
        name,
      ),
    )
  )
    throw Error("BUILDER_ASAR_UNEXPECTED_INPUT");
  for (const name of [
    "package.json",
    "dist/index.html",
    "dist-electron/main.mjs",
    "dist-electron/preload.cjs",
  ])
    if (!entries.includes(`/${name}`))
      throw Error("BUILDER_ASAR_ENTRY_MISSING");
  const pkg = JSON.parse(asar.extractFile(archive, "package.json").toString());
  if (
    pkg.main !== "dist-electron/main.mjs" ||
    pkg.type !== "module" ||
    pkg.version !== manifest.version
  )
    throw Error("BUILDER_APP_METADATA_INVALID");
  if (manifest.approvedInputs?.sourceCommit !== manifest.sourceCommit)
    throw Error("BUILDER_APPROVAL_SOURCE_MISMATCH");
  await verifyApprovedOutput(output, manifest.approvedInputs);
  return {
    files: actual.length,
    archive: archives[0],
    sourceCommit: manifest.sourceCommit,
    distributionReady: false,
    legalReviewComplete: false,
  };
}
export async function verifyApprovedOutput(output, approved) {
  if (
    !approved ||
    approved.origin !== "exclusive-clean-build" ||
    JSON.stringify(Object.keys(approved.groups)) !==
      JSON.stringify(INPUT_GROUPS)
  )
    throw Error("BUILDER_APPROVED_INPUTS_REQUIRED");
  const unpacked = join(output, "artifacts/linux-unpacked");
  for (const group of ["backend", "offline", "notices"]) {
    if (
      JSON.stringify(await treeRecords(join(unpacked, "resources", group))) !==
      JSON.stringify(approved.groups[group])
    )
      throw Error(`BUILDER_UNAPPROVED_RESOURCE: ${group}`);
  }
  const expectedVendor = approved.groups.vendor
    .flatMap((record) => {
      if (record.path === "resources/default_app.asar") return [];
      if (record.path === "electron") return [{ ...record, path: "easyai" }];
      if (record.path === "LICENSE")
        return [record, { ...record, path: "LICENSE.electron.txt" }];
      return [record];
    })
    .sort((a, b) => (a.path < b.path ? -1 : a.path > b.path ? 1 : 0));
  const actualVendor = (await treeRecords(unpacked))
    .filter(
      (r) =>
        !r.path.startsWith("resources/backend/") &&
        !r.path.startsWith("resources/offline/") &&
        !r.path.startsWith("resources/notices/") &&
        r.path !== "resources/app.asar",
    )
    .sort((a, b) => (a.path < b.path ? -1 : a.path > b.path ? 1 : 0));
  if (JSON.stringify(actualVendor) !== JSON.stringify(expectedVendor))
    throw Error("BUILDER_UNAPPROVED_VENDOR_OUTPUT");
  const archive = join(unpacked, "resources/app.asar");
  const entries = asar
    .listPackage(archive)
    .filter((name) => {
      const info = asar.statFile(archive, name.slice(1), false);
      if (info.link || info.unpacked)
        throw Error("BUILDER_ASAR_SPECIAL_FORBIDDEN");
      return !info.files;
    })
    .map((name) => name.slice(1))
    .sort();
  if (
    JSON.stringify(entries) !==
    JSON.stringify(approved.groups.app.map((r) => r.path).sort())
  )
    throw Error("BUILDER_UNAPPROVED_APP_ENTRY");
  for (const record of approved.groups.app) {
    const bytes = asar.extractFile(archive, record.path);
    if (record.path === "package.json") {
      // builder reserializes metadata. Compare its approved semantic content.
      if (JSON.stringify(JSON.parse(bytes.toString())) !== approved.appMetadata)
        throw Error("BUILDER_UNAPPROVED_APP_METADATA");
    } else if (
      bytes.length !== record.bytes ||
      createHash("sha256").update(bytes).digest("hex") !== record.sha256
    )
      throw Error("BUILDER_UNAPPROVED_APP_BYTES");
  }
}
export async function packageBuilder(root = repository) {
  if (process.platform !== "linux" || process.arch !== "x64")
    throw Error("BUILDER_PLATFORM_NOT_VALIDATED");
  const sourceCommit = execFileSync("git", ["rev-parse", "HEAD"], {
    cwd: root,
    encoding: "utf8",
  }).trim();
  const output = join(
    root,
    "dist",
    `easyai-builder-${sourceCommit.slice(0, 12)}-${Date.now()}-linux-x64`,
  );
  await mkdir(join(root, "dist"), { recursive: true });
  await mkdir(output); // Exclusive: keep existing or failed evidence, never overwrite.
  const stage = join(output, "input");
  const input = await cleanBuildInputs(root, sourceCommit);
  const approvedInputs = await stageInputs(input, stage, sourceCommit);
  const electronDist = join(stage, "vendor");
  const metadata = JSON.parse(
    await readFile(join(root, "apps/desktop/package.json"), "utf8"),
  );
  const configuration = builderConfiguration(
    stage,
    join(output, "artifacts"),
    electronDist,
    metadata.devDependencies.electron,
  );
  await build({
    projectDir: join(stage, "resources/app"),
    targets: Platform.LINUX.createTarget(["dir", "tar.gz"], Arch.x64),
    publish: "never",
    config: configuration,
  });
  for (const group of INPUT_GROUPS) {
    const path =
      group === "vendor"
        ? join(stage, "vendor")
        : join(stage, "resources", group);
    if (
      JSON.stringify(await treeRecords(path)) !==
      JSON.stringify(approvedInputs.groups[group])
    )
      throw Error("BUILDER_STAGE_CHANGED");
  }
  const unpacked = join(output, "artifacts/linux-unpacked/resources");
  const appArchive = join(unpacked, "app.asar");
  // Prove exact inputs survived ASAR and extraResources independently of builder logs.
  for (const name of [
    "dist/index.html",
    "dist-electron/main.mjs",
    "dist-electron/preload.cjs",
  ])
    if (
      !asar
        .extractFile(appArchive, name)
        .equals(await readFile(join(stage, "resources/app", name)))
    )
      throw Error("BUILDER_STALE_APP");
  for (const [source, target] of resourcePairs)
    if (
      (await hash(join(root, source))) !==
      (await hash(join(unpacked, "backend/_internal/easyai/resources", target)))
    )
      throw Error("BUILDER_STALE_RESOURCE");
  await writeFile(
    join(output, manifestName),
    JSON.stringify(
      {
        schemaVersion: 2,
        kind: "unsigned-electron-builder-local",
        version: metadata.version,
        platform: process.platform,
        arch: process.arch,
        sourceCommit,
        builderVersion: "26.15.3",
        electronVersion: metadata.devDependencies.electron,
        distributionReady: false,
        legalReviewComplete: false,
        approvedInputs,
        records: await inventory(join(output, "artifacts")),
      },
      null,
      2,
    ) + "\n",
    { flag: "wx" },
  );
  return { output, ...(await verifyBuilder(output)) };
}
if (
  process.argv[1] &&
  resolve(process.argv[1]) === fileURLToPath(import.meta.url)
) {
  const args = process.argv.slice(2);
  if (args.length === 0) console.log(await packageBuilder());
  else if (args.length === 2 && args[0] === "--verify")
    console.log(await verifyBuilder(resolve(args[1])));
  else
    throw Error(
      "Usage: pnpm package:builder | pnpm package:builder:verify -- <output>",
    );
}
