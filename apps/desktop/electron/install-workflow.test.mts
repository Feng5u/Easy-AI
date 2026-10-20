import { expect, it, vi } from "vitest";
import { MainWorkflow } from "./workflow.mjs";
import type { Backend } from "./backend.mjs";
const identity = "d6851d61-92e8-4909-b02b-2313f1fd585d";
const plan = () => ({
  targetId: "local",
  profileId: "easyai-cpu",
  packageIds: ["torch", "torchvision"],
  newEnvironmentSpec: { name: "classroom" },
});
function setup() {
  const request = vi.fn().mockResolvedValue({});
  return {
    request,
    bridge: new MainWorkflow(
      () => ({ request }) as unknown as Backend,
      vi.fn(),
      vi.fn(),
    ),
  };
}
it("installation IPC forwards fixed catalog, planning, confirmation, reads and cancel only", async () => {
  const h = setup();
  await h.bridge.invoke("easyai:packages:catalog", []);
  expect(h.request).toHaveBeenLastCalledWith("GET", "/api/v1/catalog/packages");
  await h.bridge.invoke("easyai:packages:plan", [plan()]);
  expect(h.request).toHaveBeenLastCalledWith(
    "POST",
    "/api/v1/environments/install-plan",
    plan(),
  );
  const confirmed = {
    planId: identity,
    planHash: "a".repeat(64),
    confirmed: true,
    networkAcknowledged: true,
  };
  await h.bridge.invoke("easyai:installJobs:confirm", [confirmed]);
  expect(h.request).toHaveBeenLastCalledWith(
    "POST",
    "/api/v1/install-jobs",
    confirmed,
  );
  await h.bridge.invoke("easyai:installJobs:get", [identity]);
  expect(h.request).toHaveBeenLastCalledWith(
    "GET",
    `/api/v1/install-jobs/${identity}`,
  );
  await h.bridge.invoke("easyai:installJobs:cancel", [identity]);
  expect(h.request).toHaveBeenLastCalledWith(
    "POST",
    `/api/v1/install-jobs/${identity}/cancel`,
  );
  expect(
    h.request.mock.calls.some((call) =>
      /execute|shell|pip|download/.test(String(call[1])),
    ),
  ).toBe(false);
});
it.each([
  { command: "pip install arbitrary" },
  { indexUrl: "https://arbitrary.invalid" },
  { prefix: "/teacher/shared" },
  { targetId: "ssh" },
  { profileId: "cuda" },
  { packageIds: ["torch;echo"] },
  { packageIds: ["https://arbitrary.invalid/a.whl"] },
  { packageIds: ["torch", "torch"] },
  { packageIds: [] },
  { ownedEnvironmentId: identity },
  { newEnvironmentSpec: { name: "../teacher" } },
  { newEnvironmentSpec: { name: "safe", path: "/teacher" } },
])(
  "rejects install path, shell, index, GPU or ambiguous request %j before backend",
  async (mutation) => {
    const h = setup();
    await expect(
      h.bridge.invoke("easyai:packages:plan", [{ ...plan(), ...mutation }]),
    ).rejects.toThrow();
    expect(h.request).not.toHaveBeenCalled();
  },
);
it("owned selectors are opaque IDs and confirmation requires the exact hash and explicit consent", async () => {
  const h = setup();
  await h.bridge.invoke("easyai:packages:plan", [
    { ...plan(), newEnvironmentSpec: null, ownedEnvironmentId: identity },
  ]);
  expect(h.request).toHaveBeenLastCalledWith(
    "POST",
    "/api/v1/environments/install-plan",
    {
      targetId: "local",
      profileId: "easyai-cpu",
      packageIds: plan().packageIds,
      ownedEnvironmentId: identity,
    },
  );
  h.request.mockClear();
  const value = {
    planId: identity,
    planHash: "a".repeat(64),
    confirmed: true,
    networkAcknowledged: true,
  };
  for (const raw of [
    { ...value, confirmed: false },
    { ...value, networkAcknowledged: false },
    { ...value, planHash: "bad" },
    { ...value, prefix: "/bad" },
  ])
    await expect(
      h.bridge.invoke("easyai:installJobs:confirm", [raw]),
    ).rejects.toThrow();
  await expect(
    h.bridge.invoke("easyai:installJobs:cancel", ["../bad"]),
  ).rejects.toThrow();
  await expect(
    h.bridge.invoke("easyai:packages:catalog", ["arbitrary"]),
  ).rejects.toThrow();
  expect(h.request).not.toHaveBeenCalled();
});
