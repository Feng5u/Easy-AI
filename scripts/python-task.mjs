import { spawnSync } from "node:child_process";
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
      "--paths",
      "src",
      "--add-data",
      "../../packages/block-library/manifest.json:easyai/resources",
      "--add-data",
      "../../examples/mnist-cnn/project.easyai.json:easyai/resources/templates",
      "--add-data",
      "../../runtime/entry.py:easyai/resources/runtime",
      "--add-data",
      "../../runtime/easyai_runtime.py:easyai/resources/runtime",
      "src/easyai/main.py",
    ],
  ],
};
if (!(command in operations)) throw new Error("Unknown development task");
for (const args of operations[command]) {
  const result = spawnSync("uv", ["run", "--frozen", ...args], {
    cwd: "services/backend",
    stdio: "inherit",
    shell: false,
  });
  if (result.error) throw result.error;
  if (result.status !== 0) process.exit(result.status ?? 1);
}
