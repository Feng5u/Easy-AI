import { useEffect, useRef } from "react";
import type { CompileResult, RunSource } from "../electron/bridge.js";

type Span = NonNullable<CompileResult["sourceMap"]>[number];
export function CodeView({
  code,
  spans = [],
  selectedBlock,
  onSelectBlock,
}: {
  code: string;
  spans?: Span[];
  selectedBlock?: string | null;
  onSelectBlock?: (id: string) => void;
}) {
  const selectedLine = useRef<HTMLLIElement | null>(null);
  useEffect(() => {
    selectedLine.current?.scrollIntoView({
      block: "nearest",
      inline: "nearest",
    });
  }, [selectedBlock, code]);
  const firstSelected = selectedBlock
    ? spans.find(
        (span) =>
          span.origin.blockId === selectedBlock && span.kind === "semantic",
      )?.startLine
    : undefined;
  return (
    <div className="code-view" tabIndex={0} aria-label="只读生成代码">
      <ol>
        {code.split("\n").map((text, index) => {
          const line = index + 1;
          const hits = spans.filter(
            (span) => span.startLine <= line && span.endLine >= line,
          );
          const hit = [...hits].sort(
            (left, right) =>
              Number(left.kind !== "semantic") -
                Number(right.kind !== "semantic") ||
              left.endLine - left.startLine - (right.endLine - right.startLine),
          )[0];
          const selected =
            selectedBlock &&
            hits.some((span) => span.origin.blockId === selectedBlock);
          return (
            <li
              key={line}
              ref={line === firstSelected ? selectedLine : undefined}
              className={selected ? "code-selected" : undefined}
            >
              {hit && onSelectBlock ? (
                <button
                  type="button"
                  className="code-line"
                  onClick={() => onSelectBlock(hit.origin.blockId)}
                  aria-label={`第 ${line} 行，源积木 ${hit.origin.blockId}`}
                >
                  <code>{text || " "}</code>
                </button>
              ) : (
                <code>{text || " "}</code>
              )}
            </li>
          );
        })}
      </ol>
    </div>
  );
}
export function SnapshotCode({
  source,
  selectedBlock,
  onSelectBlock,
}: {
  source: RunSource;
  selectedBlock: string | null;
  onSelectBlock: (id: string) => void;
}) {
  return (
    <section className="panel">
      <details open={Boolean(selectedBlock)}>
        <summary>
          本次运行的代码与来源 · revision {source.projectRevision}
        </summary>
        <p className="muted">
          以下代码和映射属于本次运行的保存快照。当前工程后续修改不改变这份映射。
        </p>
        {selectedBlock && (
          <p role="status">
            源积木 ID：<code>{selectedBlock}</code>
            。对应代码行已高亮；积木编辑工作区将在后续阶段提供。
          </p>
        )}
        <CodeView
          code={source.code}
          spans={source.sourceMap}
          selectedBlock={selectedBlock}
          onSelectBlock={onSelectBlock}
        />
      </details>
    </section>
  );
}
