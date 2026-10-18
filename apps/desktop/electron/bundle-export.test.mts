import { expect, it, vi } from "vitest";
import { MainWorkflow } from "./workflow.mjs";
import type { Backend } from "./backend.mjs";
import { startBackend } from "./backend.mjs";
import { mkdtemp, mkdir, readFile, readdir, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { fileURLToPath } from "node:url";

const projectId = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa";
const hash = "a".repeat(64);
const receipt = {
  exported: true,
  projectId,
  projectRevision: 1,
  programHash: hash,
  codeHash: "b".repeat(64),
  bundleHash: "c".repeat(64),
  directoryName: "easyai-code-bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb",
};
function fixture() {
  let revision = 1;
  const request = vi.fn(async (method: string, path: string) => {
    if (path === "/api/v1/local/session")
      return { project: { projectId, revision }, readOnly: false };
    if (method === "POST" && path === "/api/v1/local/export-bundle")
      return receipt;
    return null;
  });
  const backend = { request } as unknown as Backend;
  let selectedBackend: Backend | undefined = backend;
  const choose = vi.fn(
    async (): Promise<string | null> => "/native/export-parent",
  );
  const workflow = new MainWorkflow(() => selectedBackend, vi.fn(), vi.fn(), {
    importProject: vi.fn(),
    exportProject: vi.fn(),
    exportBundle: choose,
  });
  return {
    workflow,
    choose,
    request,
    setRevision: (value: number) => {
      revision = value;
    },
    retire: () => {
      selectedBackend = undefined;
    },
  };
}
it("only native Main supplies the export parent, with exact saved compilation identity", async () => {
  const { workflow, choose, request } = fixture();
  expect(
    await workflow.invoke("easyai:projects:exportBundle", [projectId, 1, hash]),
  ).toEqual(receipt);
  expect(choose).toHaveBeenCalledOnce();
  expect(request).toHaveBeenCalledWith("POST", "/api/v1/local/export-bundle", {
    projectId,
    expectedRevision: 1,
    expectedProgramHash: hash,
    parentPath: "/native/export-parent",
  });
  await expect(
    workflow.invoke("easyai:projects:exportBundle", [
      projectId,
      1,
      hash,
      "/renderer/path",
    ]),
  ).rejects.toThrow();
  await expect(
    workflow.invoke("easyai:projects:exportBundle", [projectId, 1, "bad"]),
  ).rejects.toThrow();
  expect(choose).toHaveBeenCalledOnce();
});
it("canceled picker writes nothing; stale revision or backend after picker cannot export", async () => {
  for (const change of ["cancel", "revision", "backend", "aba"]) {
    const value = fixture();
    value.choose.mockImplementation(async () => {
      if (change === "revision") value.setRevision(2);
      if (change === "backend") value.retire();
      if (change === "aba")
        await value.workflow.invoke("easyai:projects:open", [projectId]);
      return change === "cancel" ? null : "/native/export-parent";
    });
    const result = value.workflow.invoke("easyai:projects:exportBundle", [
      projectId,
      1,
      hash,
    ]);
    if (change === "cancel") expect(await result).toBeNull();
    else await expect(result).rejects.toThrow();
    expect(
      value.request.mock.calls.some(
        ([, path]) => path === "/api/v1/local/export-bundle",
      ),
    ).toBe(false);
  }
});
it("refuses foreign receipts without treating them as successful exports", async () => {
  const { workflow, request } = fixture();
  request.mockImplementation(async (_method, path) =>
    path === "/api/v1/local/session"
      ? { project: { projectId, revision: 1 }, readOnly: false }
      : { ...receipt, programHash: "d".repeat(64) },
  );
  await expect(
    workflow.invoke("easyai:projects:exportBundle", [projectId, 1, hash]),
  ).rejects.toThrow("不一致");
});
it("real Main → authenticated sidecar exports generated code and snapshot without Python/data selections", async () => {
  const directory = await mkdtemp(join(tmpdir(), "easyai-bundle-export-"));
  const cwd = fileURLToPath(
    new URL("../../../services/backend/", import.meta.url),
  );
  const backend = await startBackend(
    join(
      cwd,
      process.platform === "win32"
        ? ".venv/Scripts/python.exe"
        : ".venv/bin/python",
    ),
    cwd,
    10000,
    join(directory, "state"),
  );
  const parent = join(directory, "export-parent");
  await mkdir(parent);
  const workflow = new MainWorkflow(
    () => backend,
    async () => directory,
    vi.fn(),
    {
      importProject: vi.fn(),
      exportProject: vi.fn(),
      exportBundle: async () => parent,
    },
  );
  try {
    const selection = await backend.request<{ selectionId: string }>(
      "POST",
      "/api/v1/local/selections",
      { kind: "project", path: directory },
    );
    const session = await backend.request<{
      project: { projectId: string; revision: number };
    }>("POST", "/api/v1/projects", {
      selectionId: selection.selectionId,
      name: "export-only",
    });
    const compiled = (await workflow.invoke("easyai:projects:compile", [
      session.project,
      1,
    ])) as { runnable: boolean; programHash: string };
    expect(compiled.runnable).toBe(true);
    const result = (await workflow.invoke("easyai:projects:exportBundle", [
      session.project.projectId,
      session.project.revision,
      compiled.programHash,
    ])) as typeof receipt;
    expect(result.exported).toBe(true);
    const manifest = JSON.parse(
      await readFile(join(parent, result.directoryName, "bundle.json"), "utf8"),
    );
    expect(manifest.bundleHash).toBe(result.bundleHash);
    expect(manifest.files["code/easyai_runtime.py"]).toMatch(/^[0-9a-f]{64}$/);
    expect(manifest.files["project.easyai.json"]).toMatch(/^[0-9a-f]{64}$/);
    expect(JSON.stringify(result)).not.toContain(directory);
    expect(await readdir(parent)).toEqual([result.directoryName]);
    expect(await backend.request("GET", "/api/v1/local/activity")).toEqual({
      activeRunIds: [],
    });
  } finally {
    workflow.dispose();
    await backend.stop();
    await rm(directory, { recursive: true, force: true });
  }
}, 20000);
