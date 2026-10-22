// Packaging approvals come from fresh exclusive build outputs, never existing dist trees.
import { spawnSync, execFileSync } from "node:child_process";
import { createRequire } from "node:module";
import { randomUUID } from "node:crypto";
import {
  mkdir,
  readFile,
  writeFile,
  readdir,
  lstat,
  copyFile,
  chmod,
  rename,
  realpath,
} from "node:fs/promises";
import { join, resolve, dirname } from "node:path";
import {
  hash,
  collectNotices,
  resourcePairs,
  OFFLINE_DOCS,
} from "./package.mjs";
export const TUTORIAL_FILES = [
  "zh-CN/batch-epoch.md",
  "zh-CN/convolution.md",
  "zh-CN/dataset-loader.md",
  "zh-CN/device-environment.md",
  "zh-CN/errors-output.md",
  "zh-CN/loss-accuracy.md",
  "zh-CN/train-test.md",
];
export const INPUT_GROUPS = ["app", "backend", "offline", "notices", "vendor"];
export async function treeRecords(root, prefix = "") {
  if ((await lstat(join(root, prefix))).isSymbolicLink())
    throw Error("PACKAGE_INPUT_LINK_FORBIDDEN");
  const result = [];
  for (const name of (await readdir(join(root, prefix))).sort()) {
    const path = prefix ? `${prefix}/${name}` : name;
    const full = join(root, path),
      info = await lstat(full);
    if (info.isSymbolicLink()) throw Error("PACKAGE_INPUT_LINK_FORBIDDEN");
    if (info.isDirectory()) result.push(...(await treeRecords(root, path)));
    else if (info.isFile())
      result.push({
        path,
        bytes: info.size,
        mode: info.mode & 0o777,
        sha256: await hash(full),
      });
    else throw Error("PACKAGE_INPUT_SPECIAL_FORBIDDEN");
  }
  return result;
}
export async function validateTutorials(root) {
  const names = (await treeRecords(join(root, "tutorials")))
    .map((r) => r.path)
    .sort();
  if (JSON.stringify(names) !== JSON.stringify([...TUTORIAL_FILES].sort()))
    throw Error("PACKAGE_TUTORIAL_INPUT_UNREGISTERED");
}
export async function copyRecords(source, destination, records) {
  await mkdir(destination); // New controlled group, no adoption or merge.
  for (const record of records) {
    if (
      typeof record.path !== "string" ||
      record.path.split("/").some((p) => !p || p === "." || p === "..") ||
      record.path.includes("\\")
    )
      throw Error("PACKAGE_INPUT_PATH_INVALID");
    const target = join(destination, record.path);
    await mkdir(resolve(target, ".."), { recursive: true });
    await copyFile(join(source, record.path), target, 1);
    await chmod(target, record.mode);
  }
  if (
    JSON.stringify(await treeRecords(destination)) !== JSON.stringify(records)
  )
    throw Error("PACKAGE_INPUT_COPY_MISMATCH");
}
export async function verifyInputs(input, sourceCommit) {
  const manifest = JSON.parse(
    await readFile(join(input, "approved-inputs.json"), "utf8"),
  );
  if (
    manifest.schemaVersion !== 1 ||
    manifest.origin !== "exclusive-clean-build" ||
    manifest.sourceCommit !== sourceCommit ||
    !/^[0-9a-f]{40}$/.test(manifest.sourceCommit) ||
    JSON.stringify(Object.keys(manifest.groups)) !==
      JSON.stringify(INPUT_GROUPS)
  )
    throw Error("PACKAGE_INPUT_MANIFEST_INVALID");
  for (const group of INPUT_GROUPS) {
    const actual = await treeRecords(join(input, "payload", group));
    if (JSON.stringify(actual) !== JSON.stringify(manifest.groups[group]))
      throw Error(`PACKAGE_INPUT_UNREGISTERED_OR_CHANGED: ${group}`);
  }
  return manifest;
}
export async function stageInputs(input, stage, sourceCommit) {
  const manifest = await verifyInputs(input, sourceCommit);
  await mkdir(stage);
  await mkdir(join(stage, "resources"));
  for (const group of INPUT_GROUPS) {
    const target =
      group === "vendor"
        ? join(stage, "vendor")
        : join(stage, "resources", group);
    await copyRecords(
      join(input, "payload", group),
      target,
      manifest.groups[group],
    );
  }
  await verifyInputs(input, sourceCommit);
  return manifest;
}
function run(command, args, cwd, env = process.env) {
  const result = spawnSync(command, args, {
    cwd,
    shell: false,
    stdio: "inherit",
    env,
  });
  if (result.error) throw result.error;
  if (result.status !== 0) throw Error("PACKAGE_CLEAN_BUILD_FAILED");
}
async function put(source, destination) {
  await mkdir(resolve(destination, ".."), { recursive: true });
  await copyFile(source, destination, 1);
}
export async function newApplicationEnvironment(
  source,
  inherited = process.env,
) {
  const target = resolve(source, "services/backend/.venv");
  try {
    await lstat(target);
    throw Error("PACKAGE_BUILD_ENVIRONMENT_EXISTS");
  } catch (error) {
    if (error.code !== "ENOENT") throw error;
  }
  return {
    ...inherited,
    UV_PROJECT_ENVIRONMENT: target,
    VIRTUAL_ENV: undefined,
  };
}
function requireSource(root, sourceCommit) {
  try {
    if (
      execFileSync("git", ["rev-parse", "HEAD"], {
        cwd: root,
        encoding: "utf8",
      }).trim() !== sourceCommit
    )
      throw Error();
    execFileSync(
      "git",
      [
        "diff",
        "--quiet",
        "HEAD",
        "--",
        ".",
        ":!docs/implementation-progress.md",
      ],
      { cwd: root, stdio: "pipe" },
    );
    if (
      execFileSync("git", ["ls-files", "--others", "--exclude-standard"], {
        cwd: root,
        encoding: "utf8",
      }).trim()
    )
      throw Error();
  } catch {
    throw Error("PACKAGE_SOURCE_UNCOMMITTED_OR_CHANGED");
  }
}
export async function sourceSnapshot(root, destination, sourceCommit) {
  const entries = execFileSync("git", ["ls-tree", "-r", "-z", sourceCommit], {
    cwd: root,
    encoding: "utf8",
  })
    .split("\0")
    .filter(Boolean);
  if (
    entries.some(
      (entry) => !entry.startsWith("100644 ") && !entry.startsWith("100755 "),
    )
  )
    throw Error("PACKAGE_SOURCE_LINK_OR_SUBMODULE_FORBIDDEN");
  await mkdir(destination);
  const archive = destination + ".tar";
  execFileSync(
    "git",
    ["archive", "--format=tar", "--output", archive, sourceCommit],
    { cwd: root },
  );
  run("tar", ["-xf", archive, "-C", destination], root);
}
export async function buildPnpmCommand(
  platform = process.platform,
  pnpmHome = process.env.PNPM_HOME,
) {
  if (platform !== "win32") return { executable: "pnpm", prefix: [] };
  // pnpm/action-setup v4 registers dest/node_modules/.bin as PNPM_HOME.
  // Execute its pinned JS entry with Node; never launch a .cmd via a shell.
  if (!pnpmHome) throw Error("PACKAGE_PINNED_PNPM_UNAVAILABLE");
  const packageRoot = resolve(pnpmHome, "../pnpm");
  const metadata = JSON.parse(
    await readFile(join(packageRoot, "package.json"), "utf8"),
  );
  if (
    metadata.name !== "pnpm" ||
    metadata.version !== "11.25.0" ||
    metadata.bin?.pnpm !== "bin/pnpm.mjs"
  )
    throw Error("PACKAGE_PINNED_PNPM_UNAVAILABLE");
  const cli = join(packageRoot, metadata.bin.pnpm);
  if (!(await lstat(cli)).isFile())
    throw Error("PACKAGE_PINNED_PNPM_UNAVAILABLE");
  return { executable: process.execPath, prefix: [cli] };
}
export async function cleanBuildInputs(root, sourceCommit) {
  await validateTutorials(root); // Reject arbitrary manual additions before any build.
  requireSource(root, sourceCommit);
  await mkdir(join(root, "dist"), { recursive: true });
  const input = join(
    root,
    "dist",
    `builder-inputs-${sourceCommit.slice(0, 12)}-${randomUUID()}`,
  );
  await mkdir(input);
  const source = join(input, "source");
  const pnpm = await buildPnpmCommand();
  await sourceSnapshot(root, source, sourceCommit);
  // Install the same registered development dependencies into a REAL directory.
  // pnpm correctly refuses a symlink as its task-state node_modules root.
  const installed = JSON.parse(
    await readFile(join(root, "node_modules/.modules.yaml"), "utf8"),
  );
  const store = dirname(installed.storeDir);
  run(
    pnpm.executable,
    [
      ...pnpm.prefix,
      "install",
      "--frozen-lockfile",
      "--offline",
      "--ignore-scripts",
      "--store-dir",
      store,
    ],
    source,
    {
      ...process.env,
      XDG_DATA_HOME: process.env.XDG_DATA_HOME || dirname(dirname(store)),
    },
  );
  // A fresh application build venv avoids editable .pth fallback to the user's
  // working source. It uses the existing frozen application lock, never torch.
  run(
    "uv",
    [
      "sync",
      "--offline",
      "--frozen",
      "--project",
      join(source, "services/backend"),
      "--python",
      join(
        root,
        "services/backend/.venv",
        process.platform === "win32" ? "Scripts/python.exe" : "bin/python",
      ),
    ],
    source,
    await newApplicationEnvironment(source),
  );
  const environmentPath = join(source, "services/backend/.venv");
  const environmentInfo = await lstat(environmentPath);
  if (
    !environmentInfo.isDirectory() ||
    environmentInfo.isSymbolicLink() ||
    (await realpath(environmentPath)) !== environmentPath
  )
    throw Error("PACKAGE_BUILD_ENVIRONMENT_REPLACED");
  const payload = join(input, "payload");
  await mkdir(payload);
  const app = join(payload, "app");
  await mkdir(app);
  run(
    pnpm.executable,
    [
      ...pnpm.prefix,
      "--filter",
      "@easyai/desktop",
      "exec",
      "tsc",
      "-p",
      "tsconfig.electron.json",
      "--outDir",
      join(app, "dist-electron"),
    ],
    source,
  );
  run(
    pnpm.executable,
    [
      ...pnpm.prefix,
      "--filter",
      "@easyai/desktop",
      "exec",
      "vite",
      "build",
      "--outDir",
      join(app, "dist"),
    ],
    source,
  );
  const scratch = join(input, "python-build");
  run(
    process.execPath,
    [join(source, "scripts/python-task.mjs"), "build", scratch],
    source,
  );
  await rename(join(scratch, "dist/easyai-sidecar"), join(payload, "backend"));
  const metadata = JSON.parse(
    await readFile(join(source, "apps/desktop/package.json"), "utf8"),
  );
  await writeFile(
    join(app, "package.json"),
    JSON.stringify(
      {
        name: "easyai-desktop",
        productName: "Easy-AI",
        version: metadata.version,
        type: "module",
        main: "dist-electron/main.mjs",
        private: true,
      },
      null,
      2,
    ) + "\n",
    { flag: "wx" },
  );
  const offline = join(payload, "offline");
  await mkdir(offline);
  await validateTutorials(source);
  for (const name of TUTORIAL_FILES)
    await put(
      join(source, "tutorials", name),
      join(offline, "tutorials", name),
    );
  for (const name of OFFLINE_DOCS)
    await put(join(source, "docs", name), join(offline, "docs", name));
  await put(
    join(source, "examples/mnist-cnn/project.easyai.json"),
    join(offline, "examples/project.easyai.json"),
  );
  await collectNotices(source, join(payload, "notices"));
  // Get the registered vendor archive and extract into a NEW directory. Existing
  // installed Electron dist is not adopted or inventoried as an approved input.
  const desktopRequire = createRequire(
    join(source, "apps/desktop/package.json"),
  );
  const electronRequire = createRequire(
    desktopRequire.resolve("electron/package.json"),
  );
  const checksums = electronRequire("./checksums.json");
  const { downloadArtifact } = electronRequire("@electron/get");
  const { extract } = electronRequire("@electron-internal/extract-zip");
  const zip = await downloadArtifact({
    version: metadata.devDependencies.electron,
    artifactName: "electron",
    platform: process.platform,
    arch: process.arch,
    checksums,
    cacheRoot: join(
      process.env.XDG_CACHE_HOME || join(source, "dist/tool-cache"),
      "electron",
    ),
  });
  const vendor = join(payload, "vendor");
  await mkdir(vendor);
  await extract(zip, { dir: vendor });
  if (
    (await readFile(join(vendor, "version"), "utf8")).trim() !==
    metadata.devDependencies.electron
  )
    throw Error("PACKAGE_ELECTRON_VERSION_MISMATCH");
  for (const [sourcePath, target] of resourcePairs)
    if (
      (await hash(join(source, sourcePath))) !==
      (await hash(join(payload, "backend/_internal/easyai/resources", target)))
    )
      throw Error("PACKAGE_STALE_RESOURCE");
  requireSource(root, sourceCommit);
  await validateTutorials(root);
  // Normalize only newly generated files to the declared bundle mode policy;
  // no system helper, source checkout or security permission is changed.
  for (const group of INPUT_GROUPS)
    for (const record of await treeRecords(join(payload, group)))
      await chmod(
        join(payload, group, record.path),
        record.mode & 0o111 ? 0o755 : 0o644,
      );
  const groups = {};
  for (const group of INPUT_GROUPS)
    groups[group] = await treeRecords(join(payload, group));
  await writeFile(
    join(input, "approved-inputs.json"),
    JSON.stringify(
      {
        schemaVersion: 1,
        origin: "exclusive-clean-build",
        sourceCommit,
        electronVersion: metadata.devDependencies.electron,
        vendorArchiveSha256: await hash(zip),
        appMetadata: JSON.stringify(
          JSON.parse(await readFile(join(app, "package.json"), "utf8")),
        ),
        groups,
      },
      null,
      2,
    ) + "\n",
    { flag: "wx" },
  );
  await verifyInputs(input, sourceCommit);
  return input;
}
