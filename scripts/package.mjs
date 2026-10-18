// Offline local packaging using already installed Electron + frozen backend.
// No subprocess, package resolution, downloads, signing or publishing here.
import { createHash } from "node:crypto";
import { createReadStream } from "node:fs";
import {
  lstat,
  mkdir,
  readdir,
  readFile,
  copyFile,
  chmod,
  writeFile,
  realpath,
  link,
  unlink,
} from "node:fs/promises";
import { createRequire } from "node:module";
import { dirname, join, resolve, isAbsolute } from "node:path";
import { fileURLToPath } from "node:url";

export const OFFLINE_DOCS = [
  "developer-guide.md",
  "teacher-setup.md",
  "release-checklist.md",
  "install-contract.md",
  "install-runtime-configuration.md",
  "install-ml-sources.md",
  "install-cv-sources.md",
];
const repository = resolve(import.meta.dirname, "..");
export const defaultOutput = (root) =>
  join(root, "dist", `easyai-0.0.0-${process.platform}-${process.arch}`);
const manifestName = "package-manifest.json";
export async function hash(path) {
  const digest = createHash("sha256");
  for await (const chunk of createReadStream(path)) digest.update(chunk);
  return digest.digest("hex");
}
export async function copyTree(source, target) {
  const info = await lstat(source);
  if (info.isSymbolicLink()) throw new Error("PACKAGE_SYMLINK_FORBIDDEN");
  if (info.isDirectory()) {
    await mkdir(target, { mode: 0o700 });
    for (const name of (await readdir(source)).sort())
      await copyTree(join(source, name), join(target, name));
  } else if (info.isFile()) {
    await copyFile(source, target, 1); // COPYFILE_EXCL: never replace another writer.
    await chmod(target, info.mode & 0o777); // Preserve existing executable bits, never add setuid.
  } else throw new Error("PACKAGE_SPECIAL_FILE_FORBIDDEN");
}
async function files(root, prefix = "") {
  const result = [];
  for (const name of (await readdir(join(root, prefix))).sort()) {
    const child = prefix ? `${prefix}/${name}` : name;
    const info = await lstat(join(root, child));
    if (info.isSymbolicLink()) throw new Error("PACKAGE_SYMLINK_FORBIDDEN");
    if (info.isDirectory()) result.push(...(await files(root, child)));
    else if (info.isFile()) result.push(child);
    else throw new Error("PACKAGE_SPECIAL_FILE_FORBIDDEN");
  }
  return result;
}
async function licenseFiles(source, destination) {
  const copied = [];
  for (const name of (await readdir(source)).sort()) {
    if (!/^(licen[cs]es?|copying|notice|authors)([._-].*)?$/i.test(name))
      continue;
    await copyTree(join(source, name), join(destination, name));
    copied.push(name);
  }
  return copied;
}
async function packageRoot(owner, name) {
  const require = createRequire(join(owner, "package.json"));
  let entry;
  try {
    entry = require.resolve(`${name}/package.json`);
  } catch {
    entry = require.resolve(name);
  }
  let directory = dirname(await realpath(entry));
  while (true) {
    try {
      const value = JSON.parse(
        await readFile(join(directory, "package.json"), "utf8"),
      );
      if (value.name === name) return directory;
    } catch (error) {
      if (error.code !== "ENOENT") throw error;
    }
    const parent = dirname(directory);
    if (parent === directory)
      throw new Error("PACKAGE_DEPENDENCY_METADATA_MISSING");
    directory = parent;
  }
}
export async function collectNotices(root, output) {
  await mkdir(output, { mode: 0o700 });
  const entries = [],
    seen = new Set();
  async function javascript(owner, name) {
    const source = await packageRoot(owner, name);
    if (seen.has(source)) return;
    seen.add(source);
    const pkg = JSON.parse(
      await readFile(join(source, "package.json"), "utf8"),
    );
    const key = `js-${pkg.name.replaceAll("/", "_").replaceAll("@", "")}-${pkg.version}`;
    const destination = join(output, key);
    await mkdir(destination);
    entries.push({
      ecosystem: "javascript",
      name: pkg.name,
      version: pkg.version,
      declaredLicense: pkg.license ?? null,
      files: await licenseFiles(source, destination),
    });
    for (const child of Object.keys(pkg.dependencies ?? {}).sort())
      await javascript(source, child);
  }
  const desktop = join(root, "apps/desktop");
  const pkg = JSON.parse(await readFile(join(desktop, "package.json"), "utf8"));
  for (const name of Object.keys(pkg.dependencies).sort())
    await javascript(desktop, name);
  // Inventory all installed application distributions conservatively, including
  // dev-only packages. This is not a precise frozen dependency/legal attestation.
  const site = join(
    root,
    "services/backend/.venv",
    process.platform === "win32"
      ? "Lib/site-packages"
      : "lib/python3.11/site-packages",
  );
  for (const name of (await readdir(site))
    .filter((x) => x.endsWith(".dist-info"))
    .sort()) {
    const source = join(site, name);
    if (!(await lstat(source)).isDirectory())
      throw new Error("PACKAGE_METADATA_FORBIDDEN");
    const metadata = await readFile(join(source, "METADATA"), "utf8");
    const field = (label) =>
      metadata.match(new RegExp(`^${label}: (.+)$`, "m"))?.[1] ?? null;
    const destination = join(output, `python-${name}`);
    await mkdir(destination);
    const licenses = await licenseFiles(source, destination);
    entries.push({
      ecosystem: "python-application-environment",
      name: field("Name"),
      version: field("Version"),
      declaredLicense: field("License-Expression") ?? field("License"),
      files: licenses,
    });
  }
  await writeFile(
    join(output, "inventory.json"),
    JSON.stringify(
      {
        schemaVersion: 1,
        scope:
          "frontend dependency graph and installed application Python metadata",
        legalReviewComplete: false,
        entries,
      },
      null,
      2,
    ) + "\n",
    { flag: "wx" },
  );
  await writeFile(
    join(output, "NOTICE.txt"),
    "LOCAL VERIFICATION ARTIFACT — NOT A RELEASE\nProject license has not been declared; no project license is granted here.\nExisting third-party notices are retained, not replaced or accepted on the user's behalf.\nElectron LICENSE and LICENSES.chromium.html remain at the portable root.\nInventory includes installed application Python development distributions; exact frozen/native/system library obligations still require review.\nNo training environment, data, credentials or machine configuration is included.\n",
    { flag: "wx" },
  );
}
export const resourcePairs = [
  ["packages/block-library/manifest.json", "manifest.json"],
  ["packages/package-groups/catalog.json", "package-groups/catalog.json"],
  [
    "packages/training-profiles/easyai-cpu-sources.json",
    "training-profiles/easyai-cpu-sources.json",
  ],
  [
    "packages/training-profiles/easyai-cpu-linux-cp311.lock",
    "training-profiles/easyai-cpu-linux-cp311.lock",
  ],
  [
    "packages/training-profiles/easyai-ml-sources.json",
    "training-profiles/easyai-ml-sources.json",
  ],
  [
    "packages/training-profiles/easyai-ml-linux-cp311.lock",
    "training-profiles/easyai-ml-linux-cp311.lock",
  ],
  [
    "packages/training-profiles/easyai-cv-sources.json",
    "training-profiles/easyai-cv-sources.json",
  ],
  [
    "packages/training-profiles/easyai-cv-linux-cp311.lock",
    "training-profiles/easyai-cv-linux-cp311.lock",
  ],
  ["examples/mnist-cnn/project.easyai.json", "templates/project.easyai.json"],
  ["packages/contracts/fixtures/blank.json", "templates/blank.json"],
  ...[
    "entry.py",
    "probe.py",
    "supervisor.py",
    "portable_journal.py",
    "easyai_runtime.py",
  ].map((name) => [`runtime/${name}`, `runtime/${name}`]),
  ["services/backend/src/easyai/runtime/managed.py", "runtime/managed.py"],
];
export async function stagePortable({
  root,
  output,
  electronDist,
  notices = collectNotices,
}) {
  if (process.platform !== "linux" || process.arch !== "x64")
    throw new Error(
      "PACKAGE_PLATFORM_NOT_VALIDATED: only same-host linux-x64 portable layout is implemented",
    );
  const backend = join(root, "services/backend/dist/easyai-sidecar");
  // Fail before creating output when frozen source resources are stale.
  for (const [source, target] of resourcePairs) {
    if (
      (await hash(join(root, source))) !==
      (await hash(join(backend, "_internal/easyai/resources", target)))
    )
      throw new Error(`PACKAGE_STALE_RESOURCE: ${target}`);
  }
  const expected = JSON.parse(
    await readFile(join(root, "apps/desktop/package.json"), "utf8"),
  );
  if (
    (await readFile(join(electronDist, "version"), "utf8")).trim() !==
    expected.devDependencies.electron
  )
    throw new Error("PACKAGE_ELECTRON_VERSION_MISMATCH");
  for (const path of [
    join(electronDist, "electron"),
    join(backend, "easyai-sidecar"),
  ]) {
    const stream = createReadStream(path, { start: 0, end: 19 });
    const chunks = [];
    for await (const chunk of stream) chunks.push(chunk);
    const header = Buffer.concat(chunks);
    if (
      header.length !== 20 ||
      !header.subarray(0, 4).equals(Buffer.from([127, 69, 76, 70])) ||
      header[4] !== 2 ||
      header[5] !== 1 ||
      header.readUInt16LE(18) !== 62
    )
      throw new Error("PACKAGE_NATIVE_PLATFORM_MISMATCH");
  }
  await mkdir(dirname(output), { recursive: true });
  await copyTree(electronDist, output); // Exclusive mkdir; failed output is preserved.
  // Electron 44's app.isPackaged is false when the executable basename is
  // 'electron'. Give the copied app its product entry name; never alter the cache.
  const originalEntry = join(output, "electron");
  const originalIdentity = await lstat(originalEntry);
  await link(originalEntry, join(output, "easyai")); // Exclusive publication, no overwrite fallback.
  const currentIdentity = await lstat(originalEntry);
  if (
    currentIdentity.dev !== originalIdentity.dev ||
    currentIdentity.ino !== originalIdentity.ino
  )
    throw new Error("PACKAGE_ENTRY_REPLACED");
  await unlink(originalEntry);
  // default_app.asar is part of the vendor runtime, but an app directory takes
  // precedence; do not delete or patch the vendor runtime or sandbox helper.
  const resources = join(output, "resources");
  const app = join(resources, "app");
  await mkdir(app);
  await copyTree(join(root, "apps/desktop/dist"), join(app, "dist"));
  await copyTree(
    join(root, "apps/desktop/dist-electron"),
    join(app, "dist-electron"),
  );
  await writeFile(
    join(app, "package.json"),
    JSON.stringify(
      {
        name: "easyai-desktop",
        productName: "Easy-AI",
        version: expected.version,
        type: "module",
        main: "dist-electron/main.mjs",
        private: true,
      },
      null,
      2,
    ) + "\n",
    { flag: "wx" },
  );
  await copyTree(backend, join(resources, "backend"));
  const offline = join(resources, "offline");
  await mkdir(offline);
  await mkdir(join(offline, "docs"));
  for (const name of OFFLINE_DOCS)
    await copyTree(join(root, "docs", name), join(offline, "docs", name));
  await copyTree(join(root, "tutorials"), join(offline, "tutorials"));
  await mkdir(join(offline, "examples"));
  await copyTree(
    join(root, "examples/mnist-cnn/project.easyai.json"),
    join(offline, "examples/project.easyai.json"),
  );
  await notices(root, join(resources, "notices"));
  const records = [];
  for (const path of await files(output)) {
    const info = await lstat(join(output, path));
    records.push({
      path,
      bytes: info.size,
      sha256: await hash(join(output, path)),
      mode: info.mode & 0o777,
    });
  }
  await writeFile(
    join(output, manifestName),
    JSON.stringify(
      {
        schemaVersion: 1,
        version: expected.version,
        platform: process.platform,
        arch: process.arch,
        kind: "unsigned-local-portable",
        distributionReady: false,
        electronVersion: expected.devDependencies.electron,
        launch: "easyai",
        records,
      },
      null,
      2,
    ) + "\n",
    { flag: "wx" },
  );
  return verifyPortable(output);
}
export async function verifyPortable(output) {
  const manifest = JSON.parse(
    await readFile(join(output, manifestName), "utf8"),
  );
  if (
    manifest.schemaVersion !== 1 ||
    manifest.kind !== "unsigned-local-portable" ||
    manifest.distributionReady !== false ||
    manifest.launch !== "easyai" ||
    !Array.isArray(manifest.records)
  )
    throw new Error("PACKAGE_MANIFEST_INVALID");
  const recorded = new Set();
  for (const record of manifest.records) {
    if (
      typeof record.path !== "string" ||
      record.path.includes("\\") ||
      isAbsolute(record.path) ||
      record.path.split("/").some((x) => !x || x === "." || x === "..") ||
      recorded.has(record.path)
    )
      throw new Error("PACKAGE_MANIFEST_PATH_INVALID");
    recorded.add(record.path);
    const path = join(output, record.path),
      info = await lstat(path);
    if (
      !info.isFile() ||
      info.isSymbolicLink() ||
      info.size !== record.bytes ||
      (info.mode & 0o777) !== record.mode ||
      (await hash(path)) !== record.sha256
    )
      throw new Error(`PACKAGE_CONTENT_MISMATCH: ${record.path}`);
  }
  const actual = (await files(output)).filter((x) => x !== manifestName);
  if (actual.length !== recorded.size || actual.some((x) => !recorded.has(x)))
    throw new Error("PACKAGE_UNRECORDED_CONTENT");
  for (const required of [
    "easyai",
    "LICENSE",
    "LICENSES.chromium.html",
    "resources/app/package.json",
    "resources/app/dist/index.html",
    "resources/app/dist-electron/main.mjs",
    "resources/app/dist-electron/preload.cjs",
    "resources/backend/easyai-sidecar",
    "resources/notices/NOTICE.txt",
    "resources/notices/inventory.json",
    ...OFFLINE_DOCS.map((x) => `resources/offline/docs/${x}`),
  ])
    if (!recorded.has(required))
      throw new Error(`PACKAGE_REQUIRED_FILE_MISSING: ${required}`);
  return {
    files: recorded.size,
    platform: manifest.platform,
    arch: manifest.arch,
    distributionReady: false,
  };
}
if (
  process.argv[1] &&
  resolve(process.argv[1]) === fileURLToPath(import.meta.url)
) {
  const args = process.argv.slice(2);
  if (
    args.length > 1 ||
    args.some((x) => !["--verify", "--notices"].includes(x))
  )
    throw new Error(
      "Usage: pnpm package | pnpm package:verify | pnpm package:notices",
    );
  if (args[0] === "--notices") {
    const output = join(repository, "dist/package-notices");
    await mkdir(dirname(output), { recursive: true });
    await collectNotices(repository, output);
    console.log(
      "PASS local notices prepared; project/native license review remains incomplete",
    );
  } else if (args[0] === "--verify")
    console.log(await verifyPortable(defaultOutput(repository)));
  else
    console.log(
      await stagePortable({
        root: repository,
        output: defaultOutput(repository),
        electronDist: join(
          repository,
          "apps/desktop/node_modules/electron/dist",
        ),
      }),
    );
}
