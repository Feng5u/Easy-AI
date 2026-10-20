import { spawnSync } from "node:child_process";
const result = spawnSync(
  "uv",
  ["sync", "--frozen", "--project", "services/backend", "--python", "3.11"],
  { stdio: "inherit", shell: false },
);
if (result.error)
  throw new Error(
    "Install uv, then retry pnpm setup. Application setup never installs training packages.",
  );
if (result.status !== 0) process.exit(result.status ?? 1);
// pnpm may defer native install scripts. Use Electron's trusted installer explicitly.
const electron = spawnSync(
  process.execPath,
  ["apps/desktop/node_modules/electron/install.js"],
  { stdio: "inherit", shell: false },
);
if (electron.error) throw electron.error;
process.exit(electron.status ?? 1);
