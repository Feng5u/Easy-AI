import assert from "node:assert/strict";
import test from "node:test";
import {
  safeRequest,
  readSmokeResponse,
  stderrDiagnostics,
} from "./frozen-diagnostics.mjs";

test("HTTP diagnostics identify the route without emitting bodies or private paths", async () => {
  const request = safeRequest("GET", "/catalog/packages", 500);
  for (const body of [
    "Internal Server Error private-token",
    '{"secret":"private-token"}',
  ]) {
    await assert.rejects(
      readSmokeResponse(new Response(body, { status: 500 }), request),
      (error) => {
        assert.match(error.message, /FROZEN_HTTP_(NON_JSON|SERVER_ERROR)/);
        assert.match(error.message, /catalog\/packages/);
        assert.match(error.message, /500/);
        assert.doesNotMatch(
          error.message,
          /private-token|Internal Server Error|secret/,
        );
        return true;
      },
    );
  }
  assert.deepEqual(
    (
      await readSmokeResponse(
        new Response('{"ok":true}'),
        safeRequest("GET", "/local/session", 200),
      )
    ).value,
    { ok: true },
  );
  assert.equal(
    safeRequest("SECRET", "/private/token?q=secret").route,
    "<other>",
  );
  assert.equal(
    safeRequest(
      "POST",
      "/projects/00000000-0000-0000-0000-000000000000/compile",
    ).route,
    "/projects/:id/compile",
  );
});

test("stderr retains bounded bytes and emits only fixed file and exception labels", () => {
  const diagnostic = stderrDiagnostics(1024);
  diagnostic.append(Buffer.from("private-token".repeat(10000)));
  diagnostic.append(
    Buffer.from(
      '\n  File "C:\\private-token\\install_runtime.py", line 303, in secret_function\nAttributeError: private-token geteuid\n  File "/private/secret.py", line 9, in secret_function\nUnknownError: private-token\n',
    ),
  );
  const summary = diagnostic.summary();
  assert.equal(summary.truncated, true);
  assert.ok(summary.retainedBytes <= 1024);
  assert.deepEqual(summary.frames, [
    { file: "install_runtime.py", line: 303 },
    { file: "<other>", line: 9 },
  ]);
  assert.deepEqual(summary.exceptions, ["AttributeError"]);
  assert.doesNotMatch(
    JSON.stringify(summary),
    /private-token|secret|geteuid|UnknownError/,
  );
});
