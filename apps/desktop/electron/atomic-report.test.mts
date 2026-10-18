import { afterEach, expect, it, vi } from "vitest";
import * as fs from "node:fs/promises";
import { join } from "node:path";
import { tmpdir } from "node:os";
import { MainWorkflow } from "./workflow.mjs";
import type { Backend } from "./backend.mjs";
vi.mock("node:fs/promises", async (original) => {
  const real = await original<typeof fs>();
  return {
    ...real,
    writeFile: vi.fn(real.writeFile),
    open: vi.fn(real.open),
    link: vi.fn(real.link),
  };
});
const real = await vi.importActual<typeof fs>("node:fs/promises");
const roots: string[] = [];
afterEach(async () => {
  vi.mocked(fs.writeFile).mockImplementation(real.writeFile);
  vi.mocked(fs.open).mockImplementation(real.open);
  vi.mocked(fs.link).mockImplementation(real.link);
  await Promise.all(
    roots
      .splice(0)
      .map((path) => real.rm(path, { recursive: true, force: true })),
  );
});
const runId = "d6851d61-92e8-4909-b02b-2313f1fd585d";
const report = {
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
async function setup() {
  const root = await real.mkdtemp(join(tmpdir(), "easyai-atomic-report-"));
  roots.push(root);
  const path = join(root, "report.json");
  const request = vi.fn().mockResolvedValue(report);
  const workflow = new MainWorkflow(
    () => ({ request }) as unknown as Backend,
    vi.fn(),
    vi.fn(),
    {
      exportDiagnostic: async () => path,
      exportProject: vi.fn(),
      importProject: vi.fn(),
    },
  );
  return {
    path,
    root,
    workflow,
    invoke: () => workflow.invoke("easyai:runs:exportDiagnostic", [runId, 2]),
  };
}
it.each([false, true])(
  "partial ENOSPC write never publishes final JSON or deletes an intervening target (%s)",
  async (replaced) => {
    const h = await setup();
    let injected = 0;
    const failure = Object.assign(new Error("injected partial ENOSPC"), {
      code: "ENOSPC",
    });
    // The old implementation writes directly to the destination; the corrected one
    // writes through its exclusive staging handle. Exercise either real write path.
    vi.mocked(fs.writeFile).mockImplementationOnce(async (path) => {
      await real.writeFile(path, '{"reportVersion":');
      if (replaced) {
        await real.unlink(h.path);
        await real.writeFile(h.path, "other writer");
      }
      injected++;
      throw failure;
    });
    vi.mocked(fs.open).mockImplementationOnce(async (...args) => {
      const handle = await real.open(...args);
      vi.spyOn(handle, "writeFile").mockImplementationOnce(async () => {
        await handle.write('{"reportVersion":');
        if (replaced) await real.writeFile(h.path, "other writer");
        injected++;
        throw failure;
      });
      return handle;
    });
    await expect(h.invoke()).rejects.toMatchObject({ code: "ENOSPC" });
    expect(injected).toBe(1);
    if (replaced)
      expect(await real.readFile(h.path, "utf8")).toBe("other writer");
    else {
      await expect(real.readFile(h.path)).rejects.toMatchObject({
        code: "ENOENT",
      });
      vi.mocked(fs.writeFile).mockImplementation(real.writeFile);
      vi.mocked(fs.open).mockImplementation(real.open);
      expect(await h.invoke()).toEqual({ exported: true });
      expect(JSON.parse(await real.readFile(h.path, "utf8"))).toEqual(report);
    }
  },
);

it("a competing target created at publication is preserved and complete staging is cleaned", async () => {
  const h = await setup();
  vi.mocked(fs.link).mockImplementationOnce(async (source, target) => {
    expect(JSON.parse(await real.readFile(source, "utf8"))).toEqual(report);
    await real.writeFile(target, "competing target", { flag: "wx" });
    await real.link(source, target);
  });
  await expect(h.invoke()).rejects.toMatchObject({ code: "EEXIST" });
  expect(await real.readFile(h.path, "utf8")).toBe("competing target");
  expect(await real.readdir(h.root)).toEqual(["report.json"]);
});
it("sync failure leaves no final file, preserves the error, and permits a same-path retry", async () => {
  const h = await setup();
  vi.mocked(fs.open).mockImplementationOnce(async (...args) => {
    const handle = await real.open(...args);
    vi.spyOn(handle, "sync").mockRejectedValueOnce(
      Object.assign(new Error("injected fsync"), { code: "ENOSPC" }),
    );
    return handle;
  });
  await expect(h.invoke()).rejects.toMatchObject({ code: "ENOSPC" });
  await expect(real.readFile(h.path)).rejects.toMatchObject({ code: "ENOENT" });
  expect(await h.invoke()).toEqual({ exported: true });
  expect(JSON.parse(await real.readFile(h.path, "utf8"))).toEqual(report);
});
it("a replaced staging file is retained and a partial-write error is not swallowed", async () => {
  const h = await setup();
  let replaced = "";
  vi.mocked(fs.open).mockImplementationOnce(async (...args) => {
    const handle = await real.open(...args);
    vi.spyOn(handle, "writeFile").mockImplementationOnce(async () => {
      await handle.write("partial");
      replaced = String(args[0]);
      await real.rename(replaced, replaced + ".owned");
      await real.writeFile(replaced, "replacement staging file", {
        flag: "wx",
      });
      throw Object.assign(new Error("injected ENOSPC after replacement"), {
        code: "ENOSPC",
      });
    });
    return handle;
  });
  await expect(h.invoke()).rejects.toMatchObject({ code: "ENOSPC" });
  await expect(real.readFile(h.path)).rejects.toMatchObject({ code: "ENOENT" });
  expect(await real.readFile(replaced, "utf8")).toBe(
    "replacement staging file",
  );
});
it("scope retirement during complete staging prevents publication", async () => {
  const h = await setup();
  vi.mocked(fs.open).mockImplementationOnce(async (...args) => {
    const handle = await real.open(...args);
    const sync = handle.sync.bind(handle);
    vi.spyOn(handle, "sync").mockImplementationOnce(async () => {
      await sync();
      h.workflow.dispose();
    });
    return handle;
  });
  await expect(h.invoke()).rejects.toThrow("过期");
  await expect(real.readFile(h.path)).rejects.toMatchObject({ code: "ENOENT" });
  expect(await real.readdir(h.root)).toEqual([]);
});

it("a substituted completed staging file is neither published nor removed", async () => {
  const h = await setup();
  let substituted = "";
  vi.mocked(fs.open).mockImplementationOnce(async (...args) => {
    const handle = await real.open(...args),
      write = handle.writeFile.bind(handle);
    vi.spyOn(handle, "writeFile").mockImplementationOnce(async (...data) => {
      await write(...data);
      substituted = String(args[0]);
      await real.rename(substituted, substituted + ".owned");
      await real.writeFile(substituted, "other completed file", { flag: "wx" });
    });
    return handle;
  });
  await expect(h.invoke()).rejects.toThrow("暂存身份");
  await expect(real.readFile(h.path)).rejects.toMatchObject({ code: "ENOENT" });
  expect(await real.readFile(substituted, "utf8")).toBe("other completed file");
});
it("an unsupported exclusive link fails without falling back to partial copy or overwrite", async () => {
  const h = await setup();
  vi.mocked(fs.link).mockRejectedValueOnce(
    Object.assign(new Error("injected unsupported link"), { code: "ENOTSUP" }),
  );
  await expect(h.invoke()).rejects.toMatchObject({ code: "ENOTSUP" });
  await expect(real.readFile(h.path)).rejects.toMatchObject({ code: "ENOENT" });
  expect(await real.readdir(h.root)).toEqual([]);
});
