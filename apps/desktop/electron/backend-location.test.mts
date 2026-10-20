import { describe, it, expect } from "vitest";
import { join } from "node:path";
import { backendLocation } from "./backend-location.mjs";

describe("Main-owned backend location", () => {
  it.each(["linux", "win32", "darwin"] as const)(
    "packaged %s never falls back to checkout/Python",
    (platform) => {
      const value = backendLocation(
        true,
        "/provided resources",
        "/missing-checkout",
        platform,
      );
      expect(value.cwd).toBe(join("/provided resources", "backend"));
      expect(value.executable).toBe(
        join(
          value.cwd,
          platform === "win32" ? "easyai-sidecar.exe" : "easyai-sidecar",
        ),
      );
      expect(value.args).toEqual([]);
      expect(JSON.stringify(value)).not.toContain("missing-checkout");
    },
  );
  it("development retains the application venv module launch", () => {
    const value = backendLocation(false, "/unused", "/checkout", "linux");
    expect(value.executable).toBe(
      join("/checkout", "services/backend/.venv/bin/python"),
    );
    expect(value.args).toEqual(["-m", "easyai.main"]);
  });
});
