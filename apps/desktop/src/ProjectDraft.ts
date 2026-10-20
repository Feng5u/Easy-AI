import type { ProjectDocument, ProjectSession } from "../electron/bridge.js";

/** Serializable editor state; a response must not erase edits made while saving. */
export class ProjectDraft {
  value: ProjectDocument;
  saved: ProjectSession & { project: ProjectDocument };
  dirty = false;
  private generation = 0;
  semanticVersion = 0;
  private pending: Promise<void> | null = null;
  constructor(session: ProjectSession) {
    if (!session.project) throw new Error("Unsupported project is read-only");
    this.value = session.project;
    this.saved = { ...session, project: session.project };
  }
  edit(value: ProjectDocument, semantic = true): void {
    if (value.projectId !== this.value.projectId)
      throw new Error("Project changed");
    this.value = { ...value, revision: this.saved.project.revision };
    this.generation++;
    if (semantic) this.semanticVersion++;
    this.dirty = true;
  }
  save(
    write: (
      document: ProjectDocument,
      expected: number,
    ) => Promise<ProjectSession>,
  ): Promise<void> {
    if (this.pending) return this.pending;
    if (!this.dirty) return Promise.resolve();
    if (this.saved.readOnly)
      return Promise.reject(new Error("Project is read-only"));
    const generation = this.generation;
    const expected = this.saved.project.revision;
    const snapshot = structuredClone(this.value);
    this.pending = write(snapshot, expected)
      .then((session) => {
        if (
          !session.project ||
          session.project.projectId !== snapshot.projectId ||
          session.project.revision !== expected + 1
        )
          throw new Error("Invalid save response");
        this.saved = { ...session, project: session.project };
        this.dirty = generation !== this.generation;
        this.value = this.dirty
          ? { ...this.value, revision: session.project.revision }
          : session.project;
      })
      .finally(() => {
        this.pending = null;
      });
    return this.pending;
  }
}
