import { execFileSync } from "node:child_process";
import { mkdtempSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { fileURLToPath } from "node:url";
import { expect, it } from "vitest";

it("finishes actual Main ESM evaluation before the pinned Playwright ready gate", () => {
  const root = fileURLToPath(new URL("../../../", import.meta.url));
  const output = mkdtempSync(join(tmpdir(), "easyai-main-bootstrap-"));
  try {
    execFileSync(
      process.execPath,
      [
        "node_modules/typescript/bin/tsc",
        "-p",
        "apps/desktop/tsconfig.electron.json",
        "--outDir",
        output,
      ],
      { cwd: root, timeout: 10000 },
    );
    const result = execFileSync(
      process.execPath,
      [
        "--experimental-vm-modules",
        "scripts/main-bootstrap-probe.mjs",
        join(output, "main.mjs"),
      ],
      { cwd: root, timeout: 5000, encoding: "utf8", stdio: "pipe" },
    );
    expect(result).toContain("PASS Main evaluation -> native/PW ready");
  } finally {
    rmSync(output, { recursive: true, force: true });
  }
}, 15000);
