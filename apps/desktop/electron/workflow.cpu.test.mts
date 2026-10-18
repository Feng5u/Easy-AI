import { it, expect } from "vitest";
import {
  mkdir,
  copyFile,
  readFile,
  writeFile,
  readdir,
  stat,
} from "node:fs/promises";
import { join } from "node:path";
import { fileURLToPath } from "node:url";
import { createHash, randomUUID } from "node:crypto";
import { setTimeout as delay } from "node:timers/promises";
import { startBackend } from "./backend.mjs";
import { MainWorkflow } from "./workflow.mjs";
import type {
  SelectionKind,
  SelectionResult,
  ProjectSession,
  CompileResult,
  Run,
  ArtifactRecord,
  RunSource,
  RunLogs,
  SubscriptionMessage,
} from "./bridge.js";

const training = process.env.EASYAI_TRAINING_PYTHON;
const root = process.env.EASYAI_MAIN_TEST_ROOT;
const fixture = process.env.EASYAI_SYNTHETIC_PROJECT;
const data = process.env.EASYAI_SYNTHETIC_DATA_ROOT;
const budgetRoot = process.env.EASYAI_TRAINING_BUDGET_ROOT;
const cwd = fileURLToPath(
  new URL("../../../services/backend/", import.meta.url),
);
const appPython = join(
  cwd,
  process.platform === "win32"
    ? ".venv/Scripts/python.exe"
    : ".venv/bin/python",
);
const digest = (bytes: Uint8Array) =>
  createHash("sha256").update(bytes).digest("hex");
async function diskBytes(directory: string): Promise<number> {
  let total = 0;
  for (const entry of await readdir(directory, { withFileTypes: true })) {
    const path = join(directory, entry.name);
    if (entry.isDirectory()) total += await diskBytes(path);
    else if (entry.isFile()) total += (await stat(path)).size;
  }
  return total;
}
it.skipIf(!training || !root || !fixture || !data || !budgetRoot)(
  "real CPU bundle crosses Main workflow and authenticated sidecar using synthetic IDX",
  async () => {
    if (!training || !root || !fixture || !data || !budgetRoot)
      throw new Error("explicit opt-in required");
    expect(await diskBytes(budgetRoot)).toBeLessThan(5_000_000_000);
    await mkdir(root); // Refuse to overwrite previous evidence.
    const project = join(root, "授权 合成项目");
    await mkdir(project);
    await copyFile(fixture, join(project, "project.easyai.json"));
    const raw = join(data, "MNIST/raw");
    const dataHashes = await Promise.all(
      (await readdir(raw)).map(async (name) => [
        name,
        digest(await readFile(join(raw, name))),
      ]),
    );
    const paths: Record<SelectionKind, string> = {
      project,
      python: training,
      data,
    };
    const messages: SubscriptionMessage[] = [];
    const backend = await startBackend(
      appPython,
      cwd,
      10000,
      join(root, "state"),
    );
    const workflow = new MainWorkflow(
      () => backend,
      async (kind) => paths[kind],
      (message) => messages.push(message),
    );
    const started = Date.now();
    let run: Run | undefined;
    try {
      async function select(kind: SelectionKind) {
        return (await workflow.invoke("easyai:selections:pick", [
          kind,
        ])) as SelectionResult;
      }
      const selected = await select("project");
      const opened = (await workflow.invoke("easyai:projects:open", [
        selected.selectionId,
      ])) as ProjectSession;
      const compiled = (await workflow.invoke("easyai:projects:compile", [
        opened.project,
        1,
      ])) as CompileResult;
      expect(compiled.runnable).toBe(true);
      const request = {
        projectId: opened.project.projectId,
        expectedRevision: opened.project.revision,
        expectedProgramHash: compiled.programHash,
        pythonSelectionId: (await select("python")).selectionId,
        dataSelectionId: (await select("data")).selectionId,
        idempotencyKey: randomUUID(),
      };
      run = (await workflow.invoke("easyai:runs:start", [request])) as Run;
      const runId = run.runId;
      workflow.subscribe(randomUUID(), runId, 0);
      const duplicate = (await workflow.invoke("easyai:runs:start", [
        request,
      ])) as Run;
      expect(duplicate.runId).toBe(runId);
      while (
        !["SUCCEEDED", "FAILED", "CANCELLED", "INTERRUPTED"].includes(
          run.status,
        )
      ) {
        expect(Date.now() - started).toBeLessThan(120000);
        await delay(100);
        run = (await workflow.invoke("easyai:runs:get", [runId])) as Run;
      }
      const logs = (await workflow.invoke("easyai:runs:logs", [
        runId,
        0,
        0,
      ])) as RunLogs;
      expect(run.status, logs.stderr).toBe("SUCCEEDED");
      expect(logs.done).toBe(true);
      const deadline = Date.now() + 5000;
      while (
        !messages.some(
          (m) => m.kind === "connection" && m.state === "closed",
        ) &&
        Date.now() < deadline
      )
        await delay(25);
      const events = messages
        .filter((m) => m.kind === "event")
        .map((m) => m.event);
      expect(events.map((e) => e.seq)).toEqual(events.map((_, i) => i + 1));
      expect(events.filter((e) => e.type === "process_exited")).toHaveLength(1);
      expect(
        events.find((e) => e.type === "process_exited")?.payload.exitCode,
      ).toBe(0);
      const metrics = events.find((e) => e.type === "epoch_completed")?.payload;
      expect(metrics?.train_samples).toBe(32);
      expect(metrics?.test_samples).toBe(16);
      expect(Number.isFinite(metrics?.train_loss)).toBe(true);
      expect(
        messages.some((m) => m.kind === "connection" && m.state === "closed"),
      ).toBe(true);
      const source = (await workflow.invoke("easyai:runs:source", [
        runId,
      ])) as RunSource;
      expect(source.code).toBe(compiled.code);
      expect(source.programHash).toBe(compiled.programHash);
      expect(source.sourceMap.length).toBeGreaterThan(0);
      const artifacts = (await workflow.invoke("easyai:runs:artifacts", [
        runId,
      ])) as ArtifactRecord[];
      const figures = artifacts.filter((a) => a.kind === "figure");
      expect(figures).toHaveLength(3);
      for (const figure of figures) {
        const image = (await workflow.invoke("easyai:runs:image", [
          runId,
          figure.artifactId,
        ])) as { dataUrl: string };
        expect(image.dataUrl.startsWith("data:image/png;base64,")).toBe(true);
        const bytes = Buffer.from(image.dataUrl.split(",")[1]!, "base64");
        expect(digest(bytes)).toBe(figure.sha256);
        expect(bytes.length).toBe(figure.sizeBytes);
      }
      for (const [name, hash] of dataHashes)
        expect(digest(await readFile(join(raw, name!)))).toBe(hash);
      const report = {
        scope:
          "Main workflow + real CPU, synthetic IDX only; native picker injected, no Electron window",
        runId,
        status: run.status,
        config: run.config,
        metrics,
        eventCount: events.length,
        figures: figures.length,
        elapsedSeconds: (Date.now() - started) / 1000,
      };
      await writeFile(
        join(root, "acceptance.json"),
        JSON.stringify(report, null, 2) + "\n",
      );
      console.log(JSON.stringify(report));
    } finally {
      workflow.dispose();
      if (
        run &&
        !["SUCCEEDED", "FAILED", "CANCELLED", "INTERRUPTED"].includes(
          run.status,
        )
      )
        await backend.request("POST", `/api/v1/runs/${run.runId}/cancel`);
      await backend.stop();
    }
    expect(backend.process.exitCode).toBe(0);
    expect(await diskBytes(budgetRoot)).toBeLessThan(5_000_000_000);
  },
  150000,
);

it.skipIf(!training || !root || !fixture || !data || !budgetRoot)(
  "cancels a real CPU process through Main after runtime startup",
  async () => {
    if (!training || !root || !fixture || !data || !budgetRoot)
      throw new Error("explicit opt-in required");
    expect(await diskBytes(budgetRoot)).toBeLessThan(5_000_000_000);
    const cancelRoot = root + "-cancel";
    await mkdir(cancelRoot);
    const project = join(cancelRoot, "取消 合成项目");
    await mkdir(project);
    await copyFile(fixture, join(project, "project.easyai.json"));
    const paths: Record<SelectionKind, string> = {
      project,
      python: training,
      data,
    };
    const messages: SubscriptionMessage[] = [];
    const backend = await startBackend(
      appPython,
      cwd,
      10000,
      join(cancelRoot, "state"),
    );
    const workflow = new MainWorkflow(
      () => backend,
      async (kind) => paths[kind],
      (message) => messages.push(message),
    );
    const started = Date.now();
    let run: Run | undefined;
    try {
      const select = async (kind: SelectionKind) =>
        (await workflow.invoke("easyai:selections:pick", [
          kind,
        ])) as SelectionResult;
      const opened = (await workflow.invoke("easyai:projects:open", [
        (await select("project")).selectionId,
      ])) as ProjectSession;
      const compiled = (await workflow.invoke("easyai:projects:compile", [
        opened.project,
        1,
      ])) as CompileResult;
      run = (await workflow.invoke("easyai:runs:start", [
        {
          projectId: opened.project.projectId,
          expectedRevision: opened.project.revision,
          expectedProgramHash: compiled.programHash,
          pythonSelectionId: (await select("python")).selectionId,
          dataSelectionId: (await select("data")).selectionId,
          idempotencyKey: randomUUID(),
        },
      ])) as Run;
      const runId = run.runId;
      workflow.subscribe(randomUUID(), runId, 0);
      while (
        !messages.some(
          (m) => m.kind === "event" && m.event.type === "runtime_started",
        )
      ) {
        expect(Date.now() - started).toBeLessThan(30000);
        await delay(10);
      }
      run = (await workflow.invoke("easyai:runs:cancel", [runId])) as Run;
      while (
        !["SUCCEEDED", "FAILED", "CANCELLED", "INTERRUPTED"].includes(
          run.status,
        )
      ) {
        expect(Date.now() - started).toBeLessThan(60000);
        await delay(25);
        run = (await workflow.invoke("easyai:runs:get", [runId])) as Run;
      }
      expect(run.status).toBe("CANCELLED");
      expect(await backend.request("GET", "/api/v1/local/activity")).toEqual({
        activeRunIds: [],
      });
      const deadline = Date.now() + 5000;
      while (
        !messages.some(
          (m) => m.kind === "connection" && m.state === "closed",
        ) &&
        Date.now() < deadline
      )
        await delay(25);
      const events = messages
        .filter((m) => m.kind === "event")
        .map((m) => m.event);
      expect(events.filter((e) => e.type === "process_exited")).toHaveLength(1);
      await writeFile(
        join(cancelRoot, "acceptance.json"),
        JSON.stringify(
          {
            scope:
              "real CPU runtime startup then explicit cancel; no epoch-completion claim; native picker injected",
            runId,
            status: run.status,
            eventTypes: events.map((e) => e.type),
            managedExitEvidence:
              "unique process_exited, empty activity, clean sidecar EOF; external PID inspection unavailable in executor",
            elapsedSeconds: (Date.now() - started) / 1000,
          },
          null,
          2,
        ) + "\n",
      );
    } finally {
      workflow.dispose();
      if (
        run &&
        !["SUCCEEDED", "FAILED", "CANCELLED", "INTERRUPTED"].includes(
          run.status,
        )
      )
        await backend.request("POST", `/api/v1/runs/${run.runId}/cancel`);
      await backend.stop();
    }
    expect(backend.process.exitCode).toBe(0);
    const reopened = await startBackend(
      appPython,
      cwd,
      10000,
      join(cancelRoot, "state"),
    );
    try {
      expect(
        (await reopened.request<Run>("GET", `/api/v1/runs/${run!.runId}`))
          .status,
      ).toBe("CANCELLED");
      expect(await reopened.request("GET", "/api/v1/local/activity")).toEqual({
        activeRunIds: [],
      });
    } finally {
      await reopened.stop();
    }
    expect(await diskBytes(budgetRoot)).toBeLessThan(5_000_000_000);
  },
  90000,
);
