import { expect, it, vi } from "vitest";
import { MainWorkflow } from "./workflow.mjs";
import type { Backend } from "./backend.mjs";
import type {
  AuthenticatedConnection,
  EnvironmentCatalog,
  EnvironmentProbeResult,
} from "./bridge.js";
const projectId = "11111111-1111-4111-8111-111111111111",
  identityId = "22222222-2222-4222-8222-222222222222",
  authId = "33333333-3333-4333-8333-333333333333",
  connectionId = "44444444-4444-4444-8444-444444444444",
  envId = "55555555-5555-4555-8555-555555555555",
  requestId = "66666666-6666-4666-8666-666666666666";
const fp = "SHA256:" + "A".repeat(43),
  endpoint = { host: "synthetic.invalid", port: 22 };
function deferred<T>() {
  let resolve!: (value: T) => void;
  const promise = new Promise<T>((r) => {
    resolve = r;
  });
  return { promise, resolve };
}
function setup() {
  let current = projectId,
    connected = true;
  let trust = "trusted";
  let authDelay: Promise<unknown> | undefined,
    envDelay: Promise<unknown> | undefined,
    cancelDelay: Promise<unknown> | undefined;
  let authResponse: AuthenticatedConnection = {
    projectId,
    requestId: authId,
    identityRequestId: identityId,
    scope: { projectId, connectionId, endpoint, hostFingerprint: fp },
    username: "synthetic",
    authenticated: true,
    method: "password",
    expiresInSeconds: 300,
  };
  const catalog: EnvironmentCatalog = {
    projectId,
    connectionId,
    requestId,
    scope: authResponse.scope,
    environments: [
      {
        environmentId: envId,
        kind: "python",
        location: "/synthetic/python",
        readOnly: true,
      },
    ],
    note: "unprobed",
  };
  const probe: EnvironmentProbeResult = {
    projectId,
    connectionId,
    requestId,
    scope: authResponse.scope,
    environmentId: envId,
    environmentReady: false,
    dataReady: null,
    issues: [],
    report: {
      schemaVersion: 1,
      nonce: requestId,
      platform: "linux",
      python: {
        executable: "/synthetic/python",
        prefix: "/synthetic",
        version: [3, 11, 1],
      },
      imports: {
        torch: { imported: false, version: null, error: "missing" },
        torchvision: { imported: false, version: null, error: "missing" },
        matplotlib: { imported: false, version: null, error: "missing" },
      },
      devices: { cudaAvailable: null, mpsAvailable: null },
      tensor: {
        attempted: false,
        ok: false,
        device: "cpu",
        error: "dependency_missing",
      },
      dataset: null,
    },
  };
  const calls: { path: string; body?: unknown }[] = [];
  const request = vi.fn(
    async (_method: string, path: string, body?: unknown) => {
      // Store detached public metadata only. Test spy calls are synthetic inputs.
      calls.push({
        path,
        body: path.endsWith("/auth/password")
          ? (body as { request: unknown }).request
          : body,
      });
      if (path === "/api/v1/local/session")
        return { project: { projectId: current } };
      if (path.endsWith("/identity/probe"))
        return {
          projectId,
          requestId: identityId,
          observation: {
            endpoint,
            algorithm: "ssh-ed25519",
            fingerprint: fp,
            trustState: trust,
            challengeId: null,
            previousFingerprint: null,
          },
        };
      if (path.endsWith("/auth/password")) return authDelay ?? authResponse;
      if (path.startsWith("/api/v1/connections/session?")) return authResponse;
      if (path.endsWith("/environments/discover")) return envDelay ?? catalog;
      if (path.endsWith("/environments/probe")) return envDelay ?? probe;
      if (path.endsWith("/environments/cancel")) return cancelDelay ?? {};
      return {};
    },
  );
  const backend = { request } as unknown as Backend;
  const workflow = new MainWorkflow(
    () => (connected ? backend : undefined),
    async () => null,
    () => {},
  );
  const identity = () =>
    workflow.invoke("easyai:connections:probe", [
      projectId,
      identityId,
      endpoint,
    ]);
  const authenticate = () =>
    workflow.invoke("easyai:connections:authenticate", [
      projectId,
      authId,
      identityId,
      "synthetic",
      "synthetic-memory-only",
    ]);
  const discover = () =>
    workflow.invoke("easyai:environments:discover", [
      { projectId, connectionId, requestId, pythonPath: "/synthetic/python" },
    ]);
  return {
    workflow,
    request,
    calls,
    identity,
    authenticate,
    discover,
    catalog,
    probe,
    setAuth: (value: AuthenticatedConnection) => {
      authResponse = value;
    },
    info: authResponse,
    setTrust: (v: string) => {
      trust = v;
    },
    setProject: (v: string) => {
      current = v;
    },
    disconnect: () => {
      connected = false;
    },
    authDelay: (v: Promise<unknown>) => {
      authDelay = v;
    },
    envDelay: (v: Promise<unknown>) => {
      envDelay = v;
    },
    cancelDelay: (v: Promise<unknown>) => {
      cancelDelay = v;
    },
  };
}
async function ready(s: ReturnType<typeof setup>) {
  await s.identity();
  await s.authenticate();
}
it("requires a trusted current identity and stamps FP; password references clear after success", async () => {
  const s = setup();
  await expect(s.authenticate()).rejects.toThrow("SSH_AUTH_FAILED");
  expect(s.calls.some((c) => c.path.endsWith("/auth/password"))).toBe(false);
  await s.identity();
  const args: unknown[] = [
    projectId,
    authId,
    identityId,
    "synthetic",
    "synthetic-memory-only",
  ];
  const result = await s.workflow.invoke(
    "easyai:connections:authenticate",
    args,
  );
  expect(args[4]).toBe("");
  expect(result).toEqual(s.info);
  const call = s.request.mock.calls.find((c) =>
    c[1].endsWith("/auth/password"),
  )!;
  expect(call[2]).toEqual({
    request: {
      projectId,
      requestId: authId,
      identityRequestId: identityId,
      username: "synthetic",
      expectedFingerprint: fp,
    },
    password: "",
  });
  s.workflow.dispose();
});
it.each(["unknown", "changed"])(
  "%s identity cannot authorize password",
  async (state) => {
    const s = setup();
    s.setTrust(state);
    await s.identity().catch(() => {});
    await expect(s.authenticate()).rejects.toThrow("SSH_AUTH_FAILED");
    expect(s.calls.some((c) => c.path.endsWith("/auth/password"))).toBe(false);
    s.workflow.dispose();
  },
);
it("rejects a foreign auth scope and never adopts its connection ID", async () => {
  const s = setup();
  await s.identity();
  s.setAuth({
    ...s.info,
    scope: { ...s.info.scope, hostFingerprint: "SHA256:" + "B".repeat(43) },
  });
  await expect(s.authenticate()).rejects.toThrow("SSH_AUTH_FAILED");
  expect(s.calls.some((c) => c.path.endsWith("/auth/cancel"))).toBe(true);
  s.workflow.dispose();
});
it("cancel clears password before a late auth response and cannot revive lease", async () => {
  const s = setup(),
    delay = deferred<unknown>();
  await s.identity();
  s.authDelay(delay.promise);
  const task = s.authenticate();
  const assertion = expect(task).rejects.toThrow("SSH_AUTH_FAILED");
  await vi.waitFor(() =>
    expect(s.calls.some((c) => c.path.endsWith("/auth/password"))).toBe(true),
  );
  await s.workflow.invoke("easyai:connections:cancelAuth", [projectId, authId]);
  await assertion;
  const body = s.request.mock.calls.find((c) =>
    c[1].endsWith("/auth/password"),
  )![2];
  expect((body as { password: string }).password).toBe("");
  delay.resolve(s.info);
  await Promise.resolve();
  expect(
    await s.workflow.invoke("easyai:connections:current", [
      projectId,
      connectionId,
    ]),
  ).toBeNull();
  s.workflow.dispose();
});
it.each(["project", "backend", "dispose"])(
  "%s invalidation rejects late authentication",
  async (kind) => {
    const s = setup(),
      delay = deferred<unknown>();
    await s.identity();
    s.authDelay(delay.promise);
    const task = s.authenticate();
    const assertion = expect(task).rejects.toThrow("SSH_AUTH_FAILED");
    await vi.waitFor(() =>
      expect(s.calls.some((c) => c.path.endsWith("/auth/password"))).toBe(true),
    );
    if (kind === "project") s.setProject(envId);
    else if (kind === "backend") s.disconnect();
    else s.workflow.dispose();
    delay.resolve(s.info);
    await assertion;
    s.workflow.dispose();
  },
);
it("auth lease gates catalog and probe, exact scope/nonce and explicit interpreter", async () => {
  const s = setup();
  await ready(s);
  expect(await s.discover()).toEqual(s.catalog);
  expect(
    await s.workflow.invoke("easyai:environments:probe", [
      { projectId, connectionId, requestId, environmentId: envId },
    ]),
  ).toEqual(s.probe);
  await expect(
    s.workflow.invoke("easyai:environments:probe", [
      { projectId, connectionId, requestId, environmentId: authId },
    ]),
  ).rejects.toThrow("ENVIRONMENT_SELECTION_STALE");
  s.probe.report.nonce = authId;
  await expect(
    s.workflow.invoke("easyai:environments:probe", [
      { projectId, connectionId, requestId, environmentId: envId },
    ]),
  ).rejects.toThrow("ENVIRONMENT_FAILED");
  s.workflow.dispose();
});
it("rejects generic command, two interpreters, and foreign lease before transport", async () => {
  const s = setup();
  await ready(s);
  const before = s.calls.length;
  for (const extra of [
    { command: "ignored" },
    { pythonPath: "/p", condaPath: "/c" },
    { pythonPath: "/../escape" },
    { connectionId: envId },
  ])
    await expect(
      s.workflow.invoke("easyai:environments:discover", [
        { projectId, connectionId, requestId, ...extra },
      ]),
    ).rejects.toThrow();
  expect(s.calls.length).toBe(before);
  s.workflow.dispose();
});
it("completed old env cancel cannot close current lease; running cancel invalidates immediately", async () => {
  const s = setup();
  await ready(s);
  await s.discover();
  await s.workflow.invoke("easyai:environments:cancel", [
    { projectId, connectionId, requestId },
  ]);
  expect(
    await s.workflow.invoke("easyai:connections:current", [
      projectId,
      connectionId,
    ]),
  ).toEqual(s.info);
  const delay = deferred<unknown>(),
    cancel = deferred<unknown>();
  s.envDelay(delay.promise);
  s.cancelDelay(cancel.promise);
  const task = s.discover();
  const assertion = expect(task).rejects.toThrow("ENVIRONMENT_FAILED");
  await vi.waitFor(() =>
    expect(
      s.calls.filter((c) => c.path.endsWith("/environments/discover")).length,
    ).toBe(2),
  );
  const cancelled = s.workflow.invoke("easyai:environments:cancel", [
    { projectId, connectionId, requestId },
  ]);
  await assertion;
  expect(
    await s.workflow.invoke("easyai:connections:current", [
      projectId,
      connectionId,
    ]),
  ).toBeNull();
  cancel.resolve({});
  delay.resolve(s.catalog);
  await cancelled;
  s.workflow.dispose();
});
it("old connection close and old auth cancel leave the current lease intact", async () => {
  const s = setup();
  await ready(s);
  await s.workflow.invoke("easyai:connections:close", [projectId, envId]);
  await s.workflow.invoke("easyai:connections:cancelAuth", [projectId, envId]);
  expect(
    await s.workflow.invoke("easyai:connections:current", [
      projectId,
      connectionId,
    ]),
  ).toEqual(s.info);
  s.workflow.dispose();
});

it("late profile A update never cancels a subsequently authenticated target B", async () => {
  const h = setup(),
    save = deferred<unknown>();
  const original = h.request.getMockImplementation()!;
  const targetA = "77777777-7777-4777-8777-777777777777",
    targetB = "88888888-8888-4888-8888-888888888888";
  h.request.mockImplementation(async (method, path, body) =>
    method === "PATCH" ? save.promise : original(method, path, body),
  );
  const update = h.workflow.invoke("easyai:connections:updateProfile", [
    targetA,
    { alias: "A", endpoint, username: "synthetic", expectedRevision: 1 },
  ]);
  h.setAuth({ ...h.info, targetId: targetB, targetRevision: 1 });
  await h.identity();
  await h.workflow.invoke("easyai:connections:authenticate", [
    projectId,
    authId,
    identityId,
    "synthetic",
    "synthetic-memory-only",
    { targetId: targetB, expectedRevision: 1 },
  ]);
  expect(
    h.calls.find((call) => call.path.endsWith("/auth/password"))?.body,
  ).toEqual(expect.objectContaining({ targetId: targetB, targetRevision: 1 }));
  save.resolve({ targetId: targetA, revision: 2 });
  await update;
  const current = await h.workflow.invoke("easyai:connections:current", [
    projectId,
    connectionId,
  ]);
  expect(current).toEqual(expect.objectContaining({ targetId: targetB }));
  expect(h.calls.some((call) => call.path.endsWith("/auth/cancel"))).toBe(
    false,
  );
  h.workflow.dispose();
});

it("saved profile authentication rejects a returned foreign target", async () => {
  const h = setup();
  await h.identity();
  h.setAuth({ ...h.info, targetId: envId, targetRevision: 1 });
  await expect(
    h.workflow.invoke("easyai:connections:authenticate", [
      projectId,
      authId,
      identityId,
      "synthetic",
      "synthetic-memory-only",
      { targetId: requestId, expectedRevision: 1 },
    ]),
  ).rejects.toThrow("SSH_AUTH_FAILED");
  h.workflow.dispose();
});
