import { it, expect, vi } from "vitest";
import { ProjectDraft } from "./ProjectDraft.js";
import type { ProjectDocument, ProjectSession } from "../electron/bridge.js";
const document: ProjectDocument = {
  projectId: "project",
  name: "before",
  revision: 1,
  workspaces: {
    data: { blocks: { blocks: [] } },
    model: { blocks: { blocks: [] } },
    training: { blocks: { blocks: [] } },
  },
};
it("serializes saves and rebases concurrent edits without erasing workspace state", async () => {
  const draft = new ProjectDraft({ project: document, readOnly: false });
  draft.edit({ ...draft.value, name: "first edit" });
  let acknowledge!: (session: ProjectSession) => void;
  const write = vi.fn(
    () =>
      new Promise<ProjectSession>((resolve) => {
        acknowledge = resolve;
      }),
  );
  const first = draft.save(write);
  draft.edit({
    ...draft.value,
    name: "during save",
    ui: { activeTab: "model" },
  });
  expect(draft.save(write)).toBe(first);
  expect(write).toHaveBeenCalledTimes(1);
  const frozen = write.mock.calls[0] as unknown as [ProjectDocument, number];
  expect(frozen[0].name).toBe("first edit");
  acknowledge({ project: { ...frozen[0], revision: 2 }, readOnly: false });
  await first;
  expect(draft.value.name).toBe("during save");
  expect(draft.value.ui?.activeTab).toBe("model");
  expect(draft.value.revision).toBe(2);
  expect(draft.dirty).toBe(true);
  await draft.save(async (project, expected) => {
    expect(expected).toBe(2);
    return { project: { ...project, revision: 3 }, readOnly: false };
  });
  expect(draft.dirty).toBe(false);
  expect(draft.value.name).toBe("during save");
});
it("keeps unsaved edits and revision after a conflict, permitting an explicit retry", async () => {
  const draft = new ProjectDraft({ project: document, readOnly: false });
  draft.edit({ ...draft.value, name: "preserved" });
  await expect(
    draft.save(async () => {
      throw new Error("revision conflict");
    }),
  ).rejects.toThrow("conflict");
  expect(draft.dirty).toBe(true);
  expect(draft.value.revision).toBe(1);
  expect(draft.value.name).toBe("preserved");
  await draft.save(async (project) => ({
    project: { ...project, revision: 2 },
    readOnly: false,
  }));
  expect(draft.dirty).toBe(false);
});
it("never saves unsupported or externally locked content", async () => {
  expect(() => new ProjectDraft({ project: null, readOnly: true })).toThrow();
  const draft = new ProjectDraft({ project: document, readOnly: true });
  draft.edit({ ...document, name: "changed" });
  const write = vi.fn();
  await expect(draft.save(write)).rejects.toThrow("read-only");
  expect(write).not.toHaveBeenCalled();
});
