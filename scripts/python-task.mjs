import { spawnSync } from "node:child_process";
import { resolve, join } from "node:path";
const command = process.argv[2];
const operations = {
  check: [
    ["ruff", "check", "."],
    ["ruff", "format", "--check", "."],
    ["ruff", "check", "--config", "pyproject.toml", "../../runtime"],
    [
      "ruff",
      "format",
      "--check",
      "--config",
      "pyproject.toml",
      "../../runtime",
    ],
    ["mypy", "src"],
  ],
  test: [["pytest", "-q"]],
  build: [
    [
      "python",
      "-m",
      "PyInstaller",
      "--noconfirm",
      "--onedir",
      "--name",
      "easyai-sidecar",
      "--hidden-import",
      "easyai.services.environment_service",
      "--hidden-import",
      "easyai.services.install_process",
      "--hidden-import",
      "easyai.security.windows_store",
      "--paths",
      "src",
      "--add-data",
      "../../packages/block-library/manifest.json:easyai/resources",
      "--add-data",
      "../../packages/package-groups/catalog.json:easyai/resources/package-groups",
      "--add-data",
      "../../packages/training-profiles/easyai-cpu-sources.json:easyai/resources/training-profiles",
      "--add-data",
      "../../packages/training-profiles/easyai-cpu-linux-cp311.lock:easyai/resources/training-profiles",
      "--add-data",
      "../../packages/training-profiles/easyai-ml-sources.json:easyai/resources/training-profiles",
      "--add-data",
      "../../packages/training-profiles/easyai-ml-linux-cp311.lock:easyai/resources/training-profiles",
      "--add-data",
      "../../packages/training-profiles/easyai-cv-sources.json:easyai/resources/training-profiles",
      "--add-data",
      "../../packages/training-profiles/easyai-cv-linux-cp311.lock:easyai/resources/training-profiles",
      "--add-data",
      "../../packages/training-profiles/easyai-nlp-sources.json:easyai/resources/training-profiles",
      "--add-data",
      "../../packages/training-profiles/easyai-nlp-linux-cp311.lock:easyai/resources/training-profiles",
      "--add-data",
      "../../packages/training-profiles/easyai-dl-sources.json:easyai/resources/training-profiles",
      "--add-data",
      "../../packages/training-profiles/easyai-dl-linux-cp311.lock:easyai/resources/training-profiles",
      "--add-data",
      "../../examples/mnist-cnn/project.easyai.json:easyai/resources/templates",
      "--add-data",
      "../../packages/contracts/fixtures/blank.json:easyai/resources/templates",
      "--add-data",
      "../../runtime/entry.py:easyai/resources/runtime",
      "--add-data",
      "../../runtime/probe.py:easyai/resources/runtime",
      "--add-data",
      "../../runtime/install_owner.py:easyai/resources/runtime",
      "--add-data",
      "../../runtime/supervisor.py:easyai/resources/runtime",
      "--add-data",
      "../../runtime/portable_journal.py:easyai/resources/runtime",
      "--add-data",
      "src/easyai/runtime/managed.py:easyai/resources/runtime",
      "--add-data",
      "src/easyai/runtime/dataset_inputs.py:easyai/resources/runtime",
      "--add-data",
      "../../runtime/easyai_runtime.py:easyai/resources/runtime",
      "src/easyai/main.py",
    ],
  ],
};
if (!(command in operations)) throw new Error("Unknown development task");
if (process.argv.length > (command === "build" ? 4 : 3))
  throw Error("Invalid task arguments");
for (const original of operations[command]) {
  const args = [...original];
  if (command === "build" && process.argv[3]) {
    const output = resolve(process.argv[3]);
    // A spec in the new build directory must not reinterpret resource paths.
    for (let index = 0; index < args.length; index++) {
      if (args[index] === "--paths")
        args[index + 1] = resolve("services/backend", args[index + 1]);
      if (args[index] === "--add-data") {
        const separator = args[index + 1].indexOf(":");
        args[index + 1] =
          resolve("services/backend", args[index + 1].slice(0, separator)) +
          args[index + 1].slice(separator);
      }
    }
    args[args.length - 1] = resolve("services/backend", args.at(-1));
    args.push(
      "--distpath",
      join(output, "dist"),
      "--workpath",
      join(output, "work"),
      "--specpath",
      join(output, "spec"),
    );
  }
  const isolated = command === "build" && process.argv[3];
  const backendRoot = resolve("services/backend");
  const python = join(
    backendRoot,
    ".venv",
    process.platform === "win32" ? "Scripts/python.exe" : "bin/python",
  );
  const result = spawnSync(
    isolated ? python : "uv",
    isolated ? args.slice(1) : ["run", "--frozen", ...args],
    {
      cwd: backendRoot,
      stdio: "inherit",
      shell: false,
      env: isolated
        ? { ...process.env, PYTHONPATH: join(backendRoot, "src") }
        : process.env,
    },
  );
  if (result.error) throw result.error;
  if (result.status !== 0) process.exit(result.status ?? 1);
}
