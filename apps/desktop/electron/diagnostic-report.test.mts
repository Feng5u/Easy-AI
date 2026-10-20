import { afterEach, expect, it, vi } from "vitest";
import {
  mkdir,
  mkdtemp,
  readFile,
  rm,
  writeFile,
  symlink,
} from "node:fs/promises";
import { join } from "node:path";
import { tmpdir } from "node:os";
import { safeReport } from "./diagnostic-report.mjs";
import { MainWorkflow } from "./workflow.mjs";
import type { Backend } from "./backend.mjs";
const runId = "d6851d61-92e8-4909-b02b-2313f1fd585d";
function report() {
  return {
    reportVersion: 1,
    scope: "local_safe_summary",
    code: "RUNTIME_NAME_ERROR",
    runId,
    eventSeq: 2,
    codeHash: "b".repeat(64),
    projectRevision: 1,
    precision: "semantic",
    nameState: "registered",
    referenceCheck: "passed",
    objectsTotal: 6,
    registeredTotal: 6,
  };
}
const roots: string[] = [];
afterEach(async () => {
  await Promise.all(
    roots.splice(0).map((path) => rm(path, { recursive: true, force: true })),
  );
});
function setup(path: string | null) {
  const request = vi.fn().mockResolvedValue(report());
  const save = vi.fn().mockResolvedValue(path);
  const workflow = new MainWorkflow(
    () => ({ request }) as unknown as Backend,
    vi.fn(),
    vi.fn(),
    { exportDiagnostic: save, exportProject: vi.fn(), importProject: vi.fn() },
  );
  return { workflow, request, save };
}
async function target() {
  const root = await mkdtemp(join(tmpdir(), "easyai-report-"));
  roots.push(root);
  return join(root, "report.json");
}
function deferred<T>() {
  let resolve!: (value: T) => void;
  const promise = new Promise<T>((done) => {
    resolve = done;
  });
  return { resolve, promise };
}
it.each([
  { message: "password=private" },
  { frames: [] },
  { host: "private.invalid" },
  { nameState: "private" },
  { codeHash: "private" },
  { runId: "another-run" },
  { eventSeq: 3 },
  { projectRevision: 0 },
  { objectsTotal: 501 },
  { objectsTotal: null },
  { registeredTotal: 7 },
  { scope: "raw" },
])(
  "refuses private fields, invalid values and identity mismatch: %j",
  (mutation) => {
    expect(() => safeReport({ ...report(), ...mutation }, runId, 2)).toThrow(
      "安全校验",
    );
  },
);
it("preview is allowlisted and does not open a dialog or write files", async () => {
  const { workflow, request, save } = setup(null);
  expect(await workflow.invoke("easyai:runs:report", [runId, 2])).toEqual(
    report(),
  );
  expect(request).toHaveBeenCalledExactlyOnceWith(
    "GET",
    `/api/v1/runs/${runId}/diagnostics/2/report`,
  );
  expect(save).not.toHaveBeenCalled();
  expect(
    safeReport(
      { ...report(), objectsTotal: null, registeredTotal: null },
      runId,
      2,
    ).objectsTotal,
  ).toBeNull();
});
it("native explicit export revalidates after dialog and writes only a new local file", async () => {
  const path = await target(),
    { workflow, request, save } = setup(path);
  expect(
    await workflow.invoke("easyai:runs:exportDiagnostic", [runId, 2]),
  ).toEqual({ exported: true });
  expect(JSON.parse(await readFile(path, "utf8"))).toEqual(report());
  expect(save).toHaveBeenCalledTimes(1);
  expect(request).toHaveBeenCalledTimes(2);
  expect(request.mock.calls.every((call) => call[0] === "GET")).toBe(true);
});
it("cancelled dialog writes nothing and extra renderer path/body is rejected before I/O", async () => {
  const { workflow, request, save } = setup(null);
  for (const args of [
    [runId, 2, "/renderer/path"],
    [runId, 0],
    ["../bad", 2],
    [runId, 2, report()],
  ])
    await expect(
      workflow.invoke("easyai:runs:exportDiagnostic", args),
    ).rejects.toThrow();
  expect(request).not.toHaveBeenCalled();
  expect(save).not.toHaveBeenCalled();
  expect(
    await workflow.invoke("easyai:runs:exportDiagnostic", [runId, 2]),
  ).toEqual({ exported: false });
  expect(request).toHaveBeenCalledTimes(1);
});
it.each(["private", "changed", "revoked", "relative"])(
  "refuses %s report before creating a file",
  async (variant) => {
    const path = await target(),
      { workflow, request, save } = setup(
        variant === "relative" ? "relative.json" : path,
      );
    if (variant === "private")
      request.mockResolvedValue({ ...report(), password: "secret" });
    if (variant === "changed")
      request
        .mockResolvedValueOnce(report())
        .mockResolvedValue({ ...report(), precision: "none" });
    if (variant === "revoked")
      request
        .mockResolvedValueOnce(report())
        .mockRejectedValue(new Error("scope retired"));
    await expect(
      workflow.invoke("easyai:runs:exportDiagnostic", [runId, 2]),
    ).rejects.toThrow();
    await expect(readFile(path)).rejects.toMatchObject({ code: "ENOENT" });
    if (variant === "private") expect(save).not.toHaveBeenCalled();
  },
);
it.each(["existing", "symlink"])(
  "refuses overwriting %s target",
  async (variant) => {
    const path = await target(),
      victimRoot = path + ".directory",
      victim =
        process.platform === "win32" && variant === "symlink"
          ? join(victimRoot, "keep.txt")
          : path + ".existing";
    if (process.platform === "win32" && variant === "symlink")
      await mkdir(victimRoot);
    await writeFile(victim, "preserve private contents");
    if (variant === "symlink")
      await symlink(
        process.platform === "win32" ? victimRoot : victim,
        path,
        process.platform === "win32" ? "junction" : "file",
      );
    else await writeFile(path, "preserve report contents");
    const { workflow } = setup(path);
    await expect(
      workflow.invoke("easyai:runs:exportDiagnostic", [runId, 2]),
    ).rejects.toMatchObject({ code: "EEXIST" });
    expect(await readFile(victim, "utf8")).toBe("preserve private contents");
    if (variant === "existing")
      expect(await readFile(path, "utf8")).toBe("preserve report contents");
  },
);
it.each(["dispose", "switch"])(
  "%s invalidates a dialog in flight before writing",
  async (variant) => {
    const path = await target(),
      h = setup(path),
      dialog = deferred<string | null>();
    h.save.mockReturnValue(dialog.promise);
    const exporting = h.workflow.invoke("easyai:runs:exportDiagnostic", [
      runId,
      2,
    ]);
    await vi.waitFor(() => expect(h.save).toHaveBeenCalledTimes(1));
    if (variant === "dispose") h.workflow.dispose();
    else await h.workflow.invoke("easyai:projects:open", [runId]);
    dialog.resolve(path);
    await expect(exporting).rejects.toThrow("过期");
    await expect(readFile(path)).rejects.toMatchObject({ code: "ENOENT" });
  },
);
