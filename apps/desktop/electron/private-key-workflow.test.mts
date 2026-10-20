import { it, expect, vi } from "vitest";
import { mkdtemp, writeFile, rm, symlink } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { MainWorkflow } from "./workflow.mjs";
import { readSelectedPrivateKey } from "./private-key-file.mjs";
import type { Backend } from "./backend.mjs";
import type { AuthenticatedConnection } from "./bridge.js";

const projectId = "11111111-1111-4111-8111-111111111111",
  identityId = "22222222-2222-4222-8222-222222222222",
  requestId = "33333333-3333-4333-8333-333333333333",
  connectionId = "44444444-4444-4444-8444-444444444444";
const fingerprint = "SHA256:" + "A".repeat(43),
  endpoint = { host: "synthetic.invalid", port: 22 };
const text =
  "-----BEGIN OPENSSH PRIVATE KEY-----\nSYNTHETIC-NOT-A-REAL-KEY\n-----END OPENSSH PRIVATE KEY-----\n";
function fixture(choose: () => Promise<string | null>) {
  const info: AuthenticatedConnection = {
    projectId,
    requestId,
    identityRequestId: identityId,
    scope: { projectId, connectionId, endpoint, hostFingerprint: fingerprint },
    username: "synthetic",
    authenticated: true,
    method: "private_key",
    expiresInSeconds: 300,
  };
  let bodyRef: Record<string, unknown> | undefined,
    submissions = 0,
    current = projectId;
  const request = vi.fn(
    async (_method: string, path: string, body?: unknown) => {
      if (path.endsWith("/identity/probe"))
        return {
          projectId,
          requestId: identityId,
          observation: {
            endpoint,
            algorithm: "ssh-ed25519",
            fingerprint,
            trustState: "trusted",
            challengeId: null,
            previousFingerprint: null,
          },
        };
      if (path === "/api/v1/local/session")
        return { project: { projectId: current } };
      if (path.endsWith("/auth/private-key")) {
        submissions++;
        bodyRef = body as Record<string, unknown>;
        expect(bodyRef.privateKey).toBe(text);
        expect(bodyRef.passphrase).toBe("synthetic-phrase");
        return info;
      }
      if (path.startsWith("/api/v1/connections/session?")) return info;
      return {};
    },
  );
  const backend = { request } as unknown as Backend;
  const workflow = new MainWorkflow(
    () => backend,
    async () => null,
    () => {},
    {
      importProject: async () => null,
      exportProject: async () => null,
      privateKey: choose,
    },
  );
  return {
    workflow,
    info,
    request,
    get submissions() {
      return submissions;
    },
    get body() {
      return bodyRef;
    },
    changeProject: () => {
      current = "99999999-9999-4999-8999-999999999999";
    },
    probe: () =>
      workflow.invoke("easyai:connections:probe", [
        projectId,
        identityId,
        endpoint,
      ]),
    authenticate: () =>
      workflow.invoke("easyai:connections:authenticateKey", [
        projectId,
        requestId,
        identityId,
        "synthetic",
        "synthetic-phrase",
      ]),
  };
}
it("explicit trusted Main picker reads only selected synthetic file, submits once, clears body and supports key session scope", async () => {
  const root = await mkdtemp(join(tmpdir(), "easyai-key-main-"));
  const path = join(root, "synthetic.key");
  await writeFile(path, text);
  const choose = vi.fn(async () => path),
    value = fixture(choose);
  try {
    await value.probe();
    expect(choose).not.toHaveBeenCalled();
    expect(await value.authenticate()).toEqual(value.info);
    expect(value.submissions).toBe(1);
    expect(choose).toHaveBeenCalledTimes(1);
    expect(value.body?.privateKey).toBe("");
    expect(value.body?.passphrase).toBe("");
    expect(
      await value.workflow.invoke("easyai:connections:current", [
        projectId,
        connectionId,
      ]),
    ).toEqual(value.info);
  } finally {
    value.workflow.dispose();
    await rm(root, { recursive: true, force: true });
  }
});
it("untrusted request never opens picker; cancellation or project change while picker waits prevents secret submission", async () => {
  const choose = vi.fn(async () => null),
    untrusted = fixture(choose);
  await expect(untrusted.authenticate()).rejects.toThrow("SSH_AUTH_FAILED");
  expect(choose).not.toHaveBeenCalled();
  untrusted.workflow.dispose();
  let finish!: (path: string | null) => void;
  const picker = new Promise<string | null>((resolve) => {
    finish = resolve;
  });
  const value = fixture(() => picker);
  await value.probe();
  const pending = value.authenticate();
  await vi.waitFor(() =>
    expect(value.request).toHaveBeenCalledWith("GET", "/api/v1/local/session"),
  );
  await value.workflow.invoke("easyai:connections:cancelAuth", [
    projectId,
    requestId,
  ]);
  finish("/synthetic-not-selected-after-cancel");
  await expect(pending).rejects.toThrow("SSH_AUTH_FAILED");
  expect(value.submissions).toBe(0);
  value.workflow.dispose();
  const changed = fixture(async () => {
    changed.changeProject();
    return null;
  });
  await changed.probe();
  await expect(changed.authenticate()).rejects.toThrow("SSH_AUTH_FAILED");
  expect(changed.submissions).toBe(0);
  changed.workflow.dispose();
});
it("reader rejects directories, symlinks, oversize, invalid encoding and unsupported format without modifying originals", async () => {
  const root = await mkdtemp(join(tmpdir(), "easyai-key-read-"));
  try {
    const good = join(root, "good"),
      link = join(root, "link");
    await writeFile(good, text);
    await symlink(good, link);
    await expect(readSelectedPrivateKey(root)).rejects.toThrow();
    await expect(readSelectedPrivateKey(link)).rejects.toThrow();
    for (const [name, data] of [
      ["large", "x".repeat(65537)],
      ["bad", "not a key"],
      ["utf8", Buffer.from([255, 254])],
    ] as const) {
      const path = join(root, name);
      await writeFile(path, data);
      await expect(readSelectedPrivateKey(path)).rejects.toThrow();
    }
    expect(await readSelectedPrivateKey(good)).toBe(text);
  } finally {
    await rm(root, { recursive: true, force: true });
  }
});
