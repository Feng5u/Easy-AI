import { it, expect, vi } from "vitest";
import { IdentityWorkflow } from "./identity-workflow.mjs";
import { MainWorkflow } from "./workflow.mjs";
import type { Backend } from "./backend.mjs";
import type { IdentityResult } from "./bridge.js";

const project = "11111111-1111-4111-8111-111111111111";
const requestId = "22222222-2222-4222-8222-222222222222";
const nextId = "33333333-3333-4333-8333-333333333333";
const challenge = "44444444-4444-4444-8444-444444444444";
const fp = "SHA256:" + "A".repeat(43);
function deferred<T>() {
  let resolve!: (v: T) => void;
  const promise = new Promise<T>((r) => {
    resolve = r;
  });
  return { promise, resolve };
}
function setup() {
  let current = project;
  let state: "unknown" | "changed" | "trusted" = "unknown";
  let result: IdentityResult;
  let delay: Promise<IdentityResult> | undefined;
  const request = vi.fn(
    async (_method: string, path: string, body?: unknown): Promise<unknown> => {
      const value = body as {
        projectId: string;
        requestId: string;
        endpoint: { host: string; port: number };
      };
      if (path === "/api/v1/local/session")
        return { project: { projectId: current } };
      if (path.endsWith("/probe")) {
        result = {
          projectId: value.projectId,
          requestId: value.requestId,
          observation: {
            endpoint: value.endpoint,
            algorithm: "ssh-ed25519",
            fingerprint: fp,
            trustState: state,
            challengeId: state === "unknown" ? challenge : null,
            previousFingerprint:
              state === "changed" ? "SHA256:" + "B".repeat(43) : null,
          },
        };
        return delay ?? result;
      }
      if (path.endsWith("/confirm"))
        return {
          ...result,
          observation: {
            ...result.observation,
            challengeId: null,
            trustState: "trusted",
          },
        };
      return { cancelled: true };
    },
  );
  const backend = { request } as unknown as Backend;
  let connected: Backend | undefined = backend;
  const workflow = new IdentityWorkflow(() => connected);
  return {
    workflow,
    request,
    backend,
    setProject: (id: string) => {
      current = id;
    },
    setState: (v: typeof state) => {
      state = v;
    },
    setDelay: (v?: Promise<IdentityResult>) => {
      delay = v;
    },
    disconnect: () => {
      connected = undefined;
    },
  };
}
it("Main gates fixed fields and confirms only its displayed observation", async () => {
  const { workflow, request } = setup();
  await expect(
    workflow.invoke("easyai:connections:probe", [
      project,
      requestId,
      { host: "offline.invalid", port: 22, password: "rejected" },
    ]),
  ).rejects.toThrow();
  expect(request).not.toHaveBeenCalled();
  const result = (await workflow.invoke("easyai:connections:probe", [
    project,
    requestId,
    { host: "Offline.Invalid.", port: 22 },
  ])) as IdentityResult;
  expect(result.observation.endpoint.host).toBe("offline.invalid");
  await expect(
    workflow.invoke("easyai:connections:confirm", [
      project,
      requestId,
      "SHA256:" + "B".repeat(43),
    ]),
  ).rejects.toThrow("STALE");
  await expect(
    workflow.invoke("easyai:connections:confirm", [project, nextId, fp]),
  ).rejects.toThrow("STALE");
  const confirmed = (await workflow.invoke("easyai:connections:confirm", [
    project,
    requestId,
    fp,
  ])) as IdentityResult;
  expect(confirmed.observation.trustState).toBe("trusted");
  expect(request).toHaveBeenCalledWith(
    "POST",
    "/api/v1/connections/identity/confirm",
    {
      projectId: project,
      requestId,
      confirmation: { challengeId: challenge, fingerprint: fp },
    },
  );
});
it("Main has no changed-key override, and project/backend changes invalidate confirmation", async () => {
  const env = setup();
  env.setState("changed");
  await env.workflow.invoke("easyai:connections:probe", [
    project,
    requestId,
    { host: "offline.invalid", port: 22 },
  ]);
  await expect(
    env.workflow.invoke("easyai:connections:confirm", [project, requestId, fp]),
  ).rejects.toThrow("STALE");
  expect(
    env.request.mock.calls.some((call) => call[1].endsWith("/confirm")),
  ).toBe(false);
  env.setState("unknown");
  await env.workflow.invoke("easyai:connections:probe", [
    project,
    nextId,
    { host: "offline.invalid", port: 22 },
  ]);
  env.setProject(nextId);
  await expect(
    env.workflow.invoke("easyai:connections:confirm", [project, nextId, fp]),
  ).rejects.toThrow("PROJECT_CHANGED");
  env.setProject(project);
  await env.workflow.invoke("easyai:connections:probe", [
    project,
    requestId,
    { host: "offline.invalid", port: 22 },
  ]);
  env.disconnect();
  await expect(
    env.workflow.invoke("easyai:connections:confirm", [project, requestId, fp]),
  ).rejects.toThrow("CANCELLED");
});
it("cancel and disposal reject late responses without enabling confirmation", async () => {
  const env = setup();
  const waiting = deferred<IdentityResult>();
  env.setDelay(waiting.promise);
  const result = env.workflow.invoke("easyai:connections:probe", [
    project,
    requestId,
    { host: "offline.invalid", port: 22 },
  ]);
  const rejected = expect(result).rejects.toThrow("CANCELLED");
  await vi.waitFor(() =>
    expect(
      env.request.mock.calls.some((call) => call[1].endsWith("/probe")),
    ).toBe(true),
  );
  await env.workflow.invoke("easyai:connections:cancel", [project, requestId]);
  waiting.resolve({
    projectId: project,
    requestId,
    observation: {
      endpoint: { host: "offline.invalid", port: 22 },
      algorithm: "ssh-ed25519",
      fingerprint: fp,
      trustState: "unknown",
      challengeId: challenge,
    },
  });
  await rejected;
  await expect(
    env.workflow.invoke("easyai:connections:confirm", [project, requestId, fp]),
  ).rejects.toThrow("STALE");
  expect(env.request).toHaveBeenCalledWith(
    "POST",
    "/api/v1/connections/identity/cancel",
    { projectId: project, requestId },
  );
});
it.each([
  ["different.invalid", 22],
  ["offline.invalid", 2222],
])(
  "rejects mismatched endpoint %s:%s before any confirmation",
  async (host, port) => {
    const env = setup();
    env.setDelay(
      Promise.resolve({
        projectId: project,
        requestId,
        observation: {
          endpoint: { host, port },
          algorithm: "ssh-ed25519",
          fingerprint: fp,
          trustState: "unknown",
          challengeId: challenge,
        },
      }),
    );
    await expect(
      env.workflow.invoke("easyai:connections:probe", [
        project,
        requestId,
        { host: "offline.invalid", port: 22 },
      ]),
    ).rejects.toThrow("RESPONSE_INVALID");
    await expect(
      env.workflow.invoke("easyai:connections:confirm", [
        project,
        requestId,
        fp,
      ]),
    ).rejects.toThrow("STALE");
    expect(
      env.request.mock.calls.some((call) => call[1].endsWith("/confirm")),
    ).toBe(false);
  },
);
it.each([
  ["例子.invalid", "xn--fsqu00a.invalid"],
  ["2001:0db8:0:0::1", "2001:db8::1"],
  ["127.0.0.1", "127.0.0.1"],
])(
  "normalizes requested %s and sends the same canonical target to Python",
  async (host, canonical) => {
    const env = setup();
    const result = (await env.workflow.invoke("easyai:connections:probe", [
      project,
      requestId,
      { host, port: 2222 },
    ])) as IdentityResult;
    expect(result.observation.endpoint).toEqual({
      host: canonical,
      port: 2222,
    });
  },
);
it("MainWorkflow uses identity channels and disposal/project-open invalidation", async () => {
  const env = setup();
  const workflow = new MainWorkflow(
    () => env.backend,
    async () => null,
    () => {},
  );
  await workflow.invoke("easyai:connections:probe", [
    project,
    requestId,
    { host: "offline.invalid", port: 22 },
  ]);
  await workflow.invoke("easyai:projects:open", [project]);
  await expect(
    workflow.invoke("easyai:connections:confirm", [project, requestId, fp]),
  ).rejects.toThrow("STALE");
  await workflow.invoke("easyai:connections:probe", [
    project,
    nextId,
    { host: "offline.invalid", port: 22 },
  ]);
  workflow.dispose();
  await expect(
    workflow.invoke("easyai:connections:confirm", [project, nextId, fp]),
  ).rejects.toThrow("STALE");
});
