import { lazy, Suspense, useLayoutEffect, useMemo, useState } from "react";
import type { RunSource } from "../electron/bridge.js";
import type { WorkspaceTab } from "./editor-contract.js";
import { CodeView } from "./CodeView.js";
import { captureRunSnapshot, locateRunBlock } from "./runSnapshot.js";

const ProjectEditor = lazy(() =>
  import("./ProjectEditor.js").then((module) => ({
    default: module.ProjectEditor,
  })),
);
const ignoreChanges = () => {};
export interface SnapshotRequest {
  blockId: string;
  version: number;
}

export function SnapshotCode({
  source,
  request,
  onSelectBlock,
}: {
  source: RunSource;
  request: SnapshotRequest | null;
  onSelectBlock: (id: string | null) => void;
}) {
  const view = useMemo(() => captureRunSnapshot(source), [source]);
  const location = locateRunBlock(view, request?.blockId ?? null);
  const [tab, setTab] = useState<WorkspaceTab>(
    view.snapshot.ui?.activeTab ?? "data",
  );
  useLayoutEffect(() => {
    if (location.workspace) setTab(location.workspace);
  }, [request?.version, location.workspace]);
  return (
    <section className="panel" aria-label="本次运行的代码与积木来源">
      <details open={request !== null}>
        <summary>
          本次运行的代码与来源 · revision {source.projectRevision}
        </summary>
        <p className="muted">
          仅查看本次运行的保存快照。当前工程的改名、删除或同 ID
          新块不改变这里的来源。
        </p>
        {request && (
          <section aria-label="本次运行的只读积木快照">
            <button type="button" onClick={() => onSelectBlock(null)}>
              关闭快照，返回运行结果
            </button>
            <p>
              源积木 ID：<code>{request.blockId}</code> · 快照：
              {view.snapshot.name}
            </p>
            {location.issue && <p role="status">{location.issue}</p>}
            {!view.issue && (
              <Suspense
                fallback={<p role="status">正在打开本次运行的只读积木快照…</p>}
              >
                <ProjectEditor
                  project={view.snapshot}
                  readOnly={true}
                  selectedBlock={location.blockId}
                  activeTab={tab}
                  onTabChange={setTab}
                  onSelect={(id) => {
                    if (id) onSelectBlock(id);
                  }}
                  onChange={ignoreChanges}
                />
              </Suspense>
            )}
          </section>
        )}
        <CodeView
          code={view.code}
          spans={view.spans}
          selectedBlock={location.codeBlockId}
          onSelectBlock={onSelectBlock}
        />
      </details>
    </section>
  );
}
