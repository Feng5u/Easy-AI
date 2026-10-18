import { describe, it, expect } from "vitest";
import { fileURLToPath } from "node:url";
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
  it("reports a missing executable without hanging", async () => {
    await expect(
      startBackend("/does-not-exist/easyai", cwd, 1000),
    ).rejects.toThrow("无法启动");
  }, 5000);
});
