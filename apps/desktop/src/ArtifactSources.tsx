import { useId, useState } from "react";
import manifest from "../../../packages/block-library/manifest.json";
import type { ArtifactRecord } from "../electron/bridge.js";
import { captureRunSnapshot, locateArtifactBlock } from "./runSnapshot.js";

const labels: Record<string, string> = Object.fromEntries(
  manifest.blocks.map((block) => [block.id, block.label]),
);

export function ArtifactSources({
  artifact,
  runId,
  view,
  onLocate,
}: {
  artifact: ArtifactRecord;
  runId: string;
  view: ReturnType<typeof captureRunSnapshot> | null;
  onLocate(id: string): void;
}) {
  const configurationId = useId();
  const [expanded, setExpanded] = useState(false);
  const producer = locateArtifactBlock(
    view,
    artifact,
    runId,
    artifact.producerBlockId,
  );
  const contributors = [...new Set(artifact.contributorBlockIds)];
  return (
    <div className="artifact-sources">
      <button
        type="button"
        className="text-button"
        disabled={!producer.blockId}
        aria-describedby={
          producer.issue ? `${configurationId}-producer` : undefined
        }
        onClick={() => {
          if (producer.blockId) onLocate(producer.blockId);
        }}
      >
        来源：{artifact.producerBlockId}
      </button>
      {producer.issue && (
        <p id={`${configurationId}-producer`} className="muted">
          {producer.issue}
        </p>
      )}
      <button
        type="button"
        className="text-button"
        aria-expanded={expanded}
        aria-controls={configurationId}
        disabled={!contributors.length}
        onClick={() => setExpanded((previous) => !previous)}
      >
        查看配置
      </button>
      {!contributors.length && <p className="muted">此产物未登记配置贡献积木。</p>}
      <div id={configurationId} hidden={!expanded}>
        <p className="muted">选择此产物登记的配置，定位本次运行的只读快照。</p>
        <ul className="artifact-contributors">
          {contributors.map((id, index) => {
            const target = locateArtifactBlock(view, artifact, runId, id);
            const label = labels[view?.blockTypes.get(id) ?? ""] ?? "配置积木";
            const issueId = `${configurationId}-${index}-issue`;
            return (
              <li key={id}>
                <button
                  type="button"
                  className="text-button"
                  disabled={!target.blockId}
                  aria-describedby={target.issue ? issueId : undefined}
                  onClick={() => {
                    if (target.blockId) onLocate(target.blockId);
                  }}
                >
                  {target.blockId
                    ? `定位${label}：${id}`
                    : `配置来源 #${index + 1}（不可定位）`}
                </button>
                {target.issue && (
                  <p id={issueId} className="muted">
                    {target.issue}
                  </p>
                )}
              </li>
            );
          })}
        </ul>
      </div>
    </div>
  );
}
