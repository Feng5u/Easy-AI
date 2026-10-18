import { it, expect, vi } from "vitest";
import { MainWorkflow } from "./workflow.mjs";
import type { Backend } from "./backend.mjs";
const identity = "d6851d61-92e8-4909-b02b-2313f1fd585d";
function setup() {
  const request = vi.fn().mockResolvedValue({ selectionId: identity });
  const choose = vi.fn().mockResolvedValue("/native/authorized/path");
  const backend = {
    request,
    image: vi.fn(),
    events: vi.fn(async (_id, _after, _event, _state, signal: AbortSignal) => {
      await new Promise<void>((resolve) =>
        signal.addEventListener("abort", () => resolve(), { once: true }),
      );
    }),
  } as unknown as Backend;
  const bridge = new MainWorkflow(() => backend, choose, vi.fn());
  return { bridge, request, choose, backend };
}
it("renderer chooses only a kind, while only the native chooser supplies a path", async () => {
  const { bridge, choose, request } = setup();
  await bridge.invoke("easyai:selections:pick", ["python"]);
  expect(choose).toHaveBeenCalledWith("python");
  expect(request).toHaveBeenCalledWith("POST", "/api/v1/local/selections", {
    kind: "python",
    path: "/native/authorized/path",
  });
  await expect(
    bridge.invoke("easyai:selections:pick", ["python", "/renderer/path"]),
  ).rejects.toThrow();
});
it("rejects unknown channels, arbitrary paths, malformed ids and extra start fields", async () => {
  const { bridge, request } = setup();
  for (const [channel, args] of [
    ["easyai:fetch", ["file:///etc/passwd"]],
    ["easyai:runs:get", ["../outside"]],
    ["easyai:runs:logs", [identity, -1, 0]],
    ["easyai:runs:start", [{ path: "/bad" }]],
  ] as const) {
    await expect(bridge.invoke(channel, [...args])).rejects.toThrow();
  }
  expect(request).not.toHaveBeenCalled();
});
it("forwards only frozen start fields and a separate idempotency header", async () => {
  const { bridge, request } = setup();
  const start = {
    projectId: identity,
    expectedRevision: 2,
    expectedProgramHash: "a".repeat(64),
    pythonSelectionId: identity,
    dataSelectionId: identity,
    idempotencyKey: identity,
  };
  await bridge.invoke("easyai:runs:start", [start]);
  expect(request).toHaveBeenCalledWith(
    "POST",
    `/api/v1/projects/${identity}/runs`,
    {
      expectedRevision: 2,
      expectedProgramHash: "a".repeat(64),
      pythonSelectionId: identity,
      dataSelectionId: identity,
    },
    identity,
  );
});
it("one active subscription per window and unsubscribe abort the owned reader", async () => {
  const { bridge, backend } = setup();
  bridge.subscribe(identity, identity, 0);
  const first = vi.mocked(backend.events).mock.calls[0][4];
  const next = "bc6cc11a-d4d2-4185-a7a9-868c39bf593d";
  bridge.subscribe(next, identity, 0);
  expect(first.aborted).toBe(true);
  const second = vi.mocked(backend.events).mock.calls[1][4];
  bridge.unsubscribe(next);
  expect(second.aborted).toBe(true);
});
