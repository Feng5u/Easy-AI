import { test } from "node:test";
import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import { resolve } from "node:path";

test("candidate ZIP regressions reject traversal, aliases, types, byte and readonly drift", () => {
  const result = spawnSync(
    resolve(
      "services/backend/.venv",
      process.platform === "win32" ? "Scripts/python.exe" : "bin/python",
    ),
    ["-I", "scripts/test-candidate-archive.py"],
    { encoding: "utf8", shell: false, timeout: 15000 },
  );
  assert.equal(result.status, 0, result.stderr);
});
