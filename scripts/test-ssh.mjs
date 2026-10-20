// Explicit acceptance runner. Never installs dependencies or silently skips.
import { spawnSync } from "node:child_process";
import { existsSync } from "node:fs";
import { resolve } from "node:path";
const repository = resolve(import.meta.dirname, "..");
const python = resolve(
  repository,
  "services/backend/.venv",
  process.platform === "win32" ? "Scripts/python.exe" : "bin/python",
);
if (!existsSync(python)) {
  console.error(
    "NOT RUN [PRECHECK_FAILED]: locked backend development environment is unavailable; no installation attempted.",
  );
  process.exit(4);
}
const result = spawnSync(
  python,
  ["-I", "-B", "integration/ssh_acceptance.py", ...process.argv.slice(2)],
  {
    cwd: resolve(repository, "services/backend"),
    stdio: "inherit",
    shell: false,
  },
);
if (result.error) {
  console.error(
    "NOT RUN [PRECHECK_FAILED]: acceptance runner could not start.",
  );
  process.exit(4);
}
process.exit(result.status ?? 1);
