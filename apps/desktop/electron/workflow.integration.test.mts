import { it, expect } from "vitest";
import { mkdtemp, mkdir, readFile, writeFile, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { fileURLToPath } from "node:url";
import { startBackend } from "./backend.mjs";
import { MainWorkflow } from "./workflow.mjs";
import type {
  ProjectSession,
  SelectionResult,
  CompileResult,
} from "./bridge.js";
const cwd = fileURLToPath(
  new URL("../../../services/backend/", import.meta.url),
);
const python =
  process.platform === "win32"
    ? join(cwd, ".venv/Scripts/python.exe")
    : join(cwd, ".venv/bin/python");
it("real Main workflow crosses authenticated sidecar with opaque native selections", async () => {
  const root = await mkdtemp(join(tmpdir(), "easyai-main-"));
  const project = join(root, "授权 项目");
  await mkdir(project);
  await mkdir(join(project, "data"));
  await writeFile(join(project, "data/keep.txt"), "preserved");
  const backend = await startBackend(python, cwd, 10000, join(root, "state"));
  const workflow = new MainWorkflow(
    () => backend,
    async () => project,
    () => undefined,
  );
  try {
    expect(await workflow.invoke("easyai:projects:current", [])).toBeNull();
    const selection = (await workflow.invoke("easyai:selections:pick", [
      "project",
    ])) as SelectionResult;
    expect(selection.kind).toBe("project");
    const opened = (await workflow.invoke("easyai:projects:create", [
      selection.selectionId,
      "实际工程",
    ])) as ProjectSession;
    if (!opened.project) throw new Error("Expected compatible project");
    expect(opened.project.revision).toBe(1);
    expect(opened.readOnly).toBe(false);
    expect(await readFile(join(project, "data/keep.txt"), "utf8")).toBe(
      "preserved",
    );
    const compiled = (await workflow.invoke("easyai:projects:compile", [
      opened.project,
      1,
    ])) as CompileResult;
    expect(compiled.runnable).toBe(true);
    expect(compiled.code).toContain("loss.backward()");
    expect(Object.keys(backend)).not.toContain("token");
    expect(Object.keys(backend)).not.toContain("port");
    await expect(
      backend.request("GET", "https://example.com/escape"),
    ).rejects.toThrow("路径");
    const updated = {
      ...opened.project,
      settings: { ...opened.project.settings, executionMode: "quick" },
    };
    const saved = (await workflow.invoke("easyai:projects:save", [
      updated,
      1,
    ])) as ProjectSession;
    if (!saved.project) throw new Error("Expected saved project");
    expect(saved.project.revision).toBe(2);
    expect(saved.project.settings?.executionMode).toBe("quick");
    await expect(
      workflow.invoke("easyai:projects:save", [updated, 1]),
    ).rejects.toThrow();
    await expect(
      workflow.invoke("easyai:projects:create", [
        selection.selectionId,
        "duplicate",
      ]),
    ).rejects.toThrow();
  } finally {
    workflow.dispose();
    await backend.stop();
    await rm(root, { recursive: true, force: true });
  }
  expect(backend.process.exitCode).toBe(0);
}, 20000);
