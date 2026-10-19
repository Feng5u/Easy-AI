import { describe, it, expect } from "vitest";
import { fileURLToPath } from "node:url";
import { spawnSync } from "node:child_process";
import { realpathSync } from "node:fs";
import { resolve } from "node:path";
import { applicationPythonLaunch } from "./application-python.mjs";
import { startBackend } from "./backend.mjs";
const cwd = fileURLToPath(
  new URL("../../../services/backend/", import.meta.url),
);
const python =
  process.platform === "win32"
    ? `${cwd}/.venv/Scripts/python.exe`
    : `${cwd}/.venv/bin/python`;
describe("real sidecar lifecycle", () => {
  it("authenticates startup and exits when its parent pipe closes", async () => {
    const backend = await startBackend(python, cwd);
    expect(backend.process.pid).toBeGreaterThan(0);
    await backend.stop();
    expect(backend.process.exitCode).toBe(0);
  }, 15000);
  it("keeps application venv isolation and binds ready to the actual spawned interpreter", async () => {
    const launch = await applicationPythonLaunch(python, cwd, [
      "-m",
      "easyai.main",
    ]);
    const result = spawnSync(
      launch.executable,
      [
        "-c",
        "import os,sys,json,easyai,fastapi; print(json.dumps({'pid':os.getpid(),'prefix':sys.prefix,'basePrefix':sys.base_prefix,'executable':sys.executable,'launcherEnvRetained':'__PYVENV_LAUNCHER__' in os.environ}))",
      ],
      {
        cwd,
        env: launch.env,
        encoding: "utf8",
        timeout: 5000,
      },
    );
    expect(result.status).toBe(0);
    const report = JSON.parse(result.stdout);
    expect(report.pid).toBe(result.pid);
    expect(report.launcherEnvRetained).toBe(false);
    expect(realpathSync(report.prefix)).toBe(
      realpathSync(resolve(cwd, ".venv")),
    );
    expect(realpathSync(report.basePrefix)).not.toBe(
      realpathSync(report.prefix),
    );
    expect(resolve(report.executable).toLowerCase()).toBe(
      resolve(python).toLowerCase(),
    );
  }, 10000);
  it("still rejects a forwarding process PID even when it relays the genuine sidecar", async () => {
    // Same stdio-inheritance/CreateProcess/wait shape as a Windows venv redirector.
    const script =
      "import subprocess,sys; p=subprocess.Popen([sys.executable,'-m','easyai.main'],stdin=sys.stdin,stdout=sys.stdout,stderr=sys.stderr); sys.exit(p.wait())";
    await expect(
      startBackend(python, cwd, 5000, undefined, ["-c", script]),
    ).rejects.toThrow("启动协议不匹配");
  }, 15000);
  it("reports a missing executable without hanging", async () => {
    await expect(
      startBackend("/does-not-exist/easyai", cwd, 1000),
    ).rejects.toThrow("无法启动");
  }, 5000);
});
