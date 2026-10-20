import type { ArtifactRecord, RunSource } from "../electron/bridge.js";
import type { WorkspaceTab } from "./editor-contract.js";
import { freezeSourceMap } from "./monaco-mapping.js";

export function captureRunSnapshot(source: RunSource) {
  const snapshot = structuredClone(source.snapshot);
  const lines = source.code.split("\n").length;
  const spans = freezeSourceMap(source.sourceMap).filter(
    (span) => (span.file ?? "train.py") === "train.py" && span.endLine <= lines,
  );
  const blocks = new Map<string, WorkspaceTab>();
  const blockTypes = new Map<string, string>();
  let issue = "";
  if (
    (snapshot.schemaVersion ?? 1) !== 1 ||
    (snapshot.blockLibraryVersion ?? "0.0.0") !== "0.0.0"
  )
    issue =
      "此旧运行的工程或积木库版本尚不支持，只保留旧代码；不会定位到当前工程。";
  else if (snapshot.revision !== source.projectRevision)
    issue = "运行快照与代码版本不一致，不能定位积木；不会使用当前工程替代。";
  if (!issue) {
    for (const tab of ["data", "model", "training"] as const) {
      const pending: unknown[] = [
        ...(snapshot.workspaces[tab]?.blocks.blocks ?? []),
      ];
      let visited = 0;
      while (pending.length) {
        if (++visited > 10_000) {
          issue = "旧运行快照结构超限，无法显示积木。";
          break;
        }
        const raw = pending.pop();
        if (!raw || typeof raw !== "object") continue;
        const block = raw as Record<string, unknown>;
        if (typeof block.id === "string") {
          if (blocks.has(block.id))
            issue = "旧运行包含重复积木 ID，不能可靠定位。";
          blocks.set(block.id, tab);
          if (typeof block.type === "string")
            blockTypes.set(block.id, block.type);
        }
        if (block.next && typeof block.next === "object")
          pending.push((block.next as Record<string, unknown>).block);
        if (block.inputs && typeof block.inputs === "object")
          for (const input of Object.values(block.inputs)) {
            if (input && typeof input === "object") {
              pending.push(input.block, input.shadow);
            }
          }
      }
    }
  }
  return { snapshot, spans, blocks, blockTypes, issue, code: source.code };
}

export function locateArtifactBlock(
  view: ReturnType<typeof captureRunSnapshot> | null,
  artifact: ArtifactRecord,
  runId: string,
  id: string,
) {
  if (artifact.runId !== runId)
    return { blockId: null, issue: "此产物不属于本次运行，不能定位来源。" };
  if (!view)
    return { blockId: null, issue: "本次运行的来源尚未核验，暂不能定位。" };
  if (
    id !== artifact.producerBlockId &&
    !artifact.contributorBlockIds.includes(id)
  )
    return { blockId: null, issue: "此积木未登记为该产物的来源。" };
  const location = locateRunBlock(view, id);
  return {
    blockId: location.codeBlockId ? location.blockId : null,
    issue:
      location.issue ||
      (location.codeBlockId ? "" : "此来源缺少可核验的积木和代码映射，不能定位。"),
  };
}

export function locateRunBlock(
  view: ReturnType<typeof captureRunSnapshot>,
  id: string | null,
) {
  if (view.issue || !id)
    return {
      blockId: null,
      codeBlockId: null,
      workspace: null,
      issue: view.issue,
    };
  const workspace = view.blocks.get(id);
  if (!workspace)
    return {
      blockId: null,
      codeBlockId: null,
      workspace: null,
      issue: "该源积木不在此运行快照中，不能定位；不会查找当前工程的同名 ID。",
    };
  const spans = view.spans.filter((span) => span.origin.blockId === id);
  if (spans.some((span) => span.origin.workspace !== workspace))
    return {
      blockId: null,
      codeBlockId: null,
      workspace: null,
      issue: "旧运行映射与快照标签页不一致，已停止定位。",
    };
  return {
    blockId: id,
    codeBlockId: spans.length ? id : null,
    workspace,
    issue: spans.length
      ? ""
      : "旧运行缺少此积木的代码映射；仅定位快照积木，不猜测代码行。",
  };
}
