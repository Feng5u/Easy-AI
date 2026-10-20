import { expect, it, vi } from "vitest";
import { MainWorkflow } from "./workflow.mjs";
import type { Backend } from "./backend.mjs";
const identity = "d6851d61-92e8-4909-b02b-2313f1fd585d",
  hash = "a".repeat(64);
function setup(
  pick = vi.fn(async (): Promise<string | null> => "/native/operator.json"),
) {
  const request = vi.fn(
    async (_method: string, path: string, _body?: unknown) =>
      path.endsWith("preview")
        ? { previewId: identity, previewHash: hash }
        : { previewId: identity, executionEnabled: false },
  );
  const backend = { request } as unknown as Backend;
  const current = { value: backend as Backend | undefined };
  const workflow = new MainWorkflow(() => current.value, vi.fn(), vi.fn(), {
    importProject: vi.fn(),
    exportProject: vi.fn(),
    installSources: pick,
  });
  return { workflow, pick, request, current };
}
const confirmation = () => ({
  previewId: identity,
  previewHash: hash,
  confirmed: true,
});
it("only Main's native-selected manifest becomes a readonly preview; explicit exact receipt confirms registration", async () => {
  const h = setup();
  await h.workflow.invoke("easyai:packages:chooseSources", [
    { packageIds: ["torch"] },
  ]);
  expect(h.request).toHaveBeenLastCalledWith(
    "POST",
    "/api/v1/environments/install-source/preview",
    { manifestPath: "/native/operator.json", packageIds: ["torch"] },
  );
  expect(h.request).toHaveBeenCalledTimes(1);
  await h.workflow.invoke("easyai:packages:confirmSources", [confirmation()]);
  expect(h.request).toHaveBeenLastCalledWith(
    "POST",
    "/api/v1/environments/install-source/confirm",
    confirmation(),
  );
  expect(JSON.stringify(h.request.mock.calls)).not.toMatch(
    /executionAuthorized|execute|pip/,
  );
});
it.each([
  { packageIds: ["torch"], manifestPath: "/renderer/arbitrary" },
  { packageIds: ["torch"], command: "run" },
  { packageIds: ["torch"], executionAuthorized: true },
  { packageIds: [] },
  { packageIds: ["torch", "torch"] },
  { packageIds: ["../path"] },
])("rejects renderer authority or path before picker: %j", async (raw) => {
  const h = setup();
  await expect(
    h.workflow.invoke("easyai:packages:chooseSources", [raw]),
  ).rejects.toThrow();
  expect(h.pick).not.toHaveBeenCalled();
  expect(h.request).not.toHaveBeenCalled();
});
it("cancellation leaves current configuration untouched and cannot confirm an older receipt", async () => {
  const pick = vi.fn(async (): Promise<string | null> => "/native/source.json"),
    h = setup(pick);
  await h.workflow.invoke("easyai:packages:chooseSources", [
    { packageIds: ["torch"] },
  ]);
  h.request.mockClear();
  pick.mockResolvedValue(null);
  expect(
    await h.workflow.invoke("easyai:packages:chooseSources", [
      { packageIds: ["torch"] },
    ]),
  ).toBeNull();
  await expect(
    h.workflow.invoke("easyai:packages:confirmSources", [confirmation()]),
  ).rejects.toThrow();
  expect(h.request).not.toHaveBeenCalled();
});
it("missing preview, false confirmation, extra paths and wrong hash cannot register", async () => {
  const h = setup();
  await expect(
    h.workflow.invoke("easyai:packages:confirmSources", [confirmation()]),
  ).rejects.toThrow();
  await h.workflow.invoke("easyai:packages:chooseSources", [
    { packageIds: ["torch"] },
  ]);
  h.request.mockClear();
  for (const value of [
    { ...confirmation(), confirmed: false },
    { ...confirmation(), confirmed: 1 },
    { ...confirmation(), previewHash: "b".repeat(64) },
    { ...confirmation(), manifestPath: "/bad" },
  ])
    await expect(
      h.workflow.invoke("easyai:packages:confirmSources", [value]),
    ).rejects.toThrow();
  expect(h.request).not.toHaveBeenCalled();
});
it("backend change while picker waits cannot submit a selected pathname", async () => {
  let release!: (value: string | null) => void;
  const h = setup(
    vi.fn(
      () =>
        new Promise<string | null>((resolve) => {
          release = resolve;
        }),
    ),
  );
  const pending = h.workflow.invoke("easyai:packages:chooseSources", [
    { packageIds: ["torch"] },
  ]);
  h.current.value = undefined;
  release("/native/source.json");
  await expect(pending).rejects.toThrow();
  expect(h.request).not.toHaveBeenCalled();
});
it("late confirmation after disposal is reported uncertain, never returned as current success", async () => {
  const h = setup();
  await h.workflow.invoke("easyai:packages:chooseSources", [
    { packageIds: ["torch"] },
  ]);
  let release!: (value: unknown) => void;
  h.request.mockImplementationOnce(
    () =>
      new Promise((resolve) => {
        release = resolve;
      }) as never,
  );
  const pending = h.workflow.invoke("easyai:packages:confirmSources", [
    confirmation(),
  ]);
  h.workflow.dispose();
  release({ previewId: identity, executionEnabled: false });
  await expect(pending).rejects.toThrow(/会话已变化/);
});
