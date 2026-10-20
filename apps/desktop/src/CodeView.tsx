import { useEffect, useMemo, useRef, useState } from "react";
import { freezeSourceMap, sourceAtLine } from "./monaco-mapping.js";
import { createReadOnlyCodeController } from "./monaco-controller.js";
import type { ReadOnlyCodeController } from "./monaco-controller.js";
import type { CompileResult } from "../electron/bridge.js";

type Span = NonNullable<CompileResult["sourceMap"]>[number];
export function CodeView({
  code,
  spans = [],
  selectedBlock,
  onSelectBlock,
  navigationVersion,
}: {
  code: string;
  spans?: readonly Span[];
  selectedBlock?: string | null;
  onSelectBlock?: (id: string) => void;
  navigationVersion?: number;
}) {
  const host = useRef<HTMLDivElement | null>(null);
  const controller = useRef<ReadOnlyCodeController | null>(null);
  const latest = useRef({
    code,
    spans,
    selectedBlock,
    onSelectBlock,
    navigationVersion,
  });
  latest.current = {
    code,
    spans,
    selectedBlock,
    onSelectBlock,
    navigationVersion,
  };
  const [ready, setReady] = useState(false);
  const [failure, setFailure] = useState("");
  const immutableMap = useMemo(() => freezeSourceMap(spans), [spans]);
  useEffect(() => {
    const element = host.current;
    if (!element) return;
    let active = true;
    let loading = false;
    const initialize = () => {
      if (controller.current) {
        controller.current.layout();
        return;
      }
      if (
        loading ||
        !element.getClientRects().length ||
        element.clientWidth === 0
      )
        return;
      const nonce = element.ownerDocument.querySelector<HTMLMetaElement>(
        'meta[name="easyai-style-nonce"]',
      )?.content;
      if (!nonce || !/^(?:[a-f0-9]{64}|[A-Za-z0-9+/]{43}=)$/.test(nonce)) {
        setFailure("代码编辑器缺少本页受控样式授权，以下保留纯文本只读内容。");
        loading = true;
        return;
      }
      loading = true;
      void import("./monaco-loader.js")
        .then(({ monaco }) => {
          if (!active) return;
          const current = latest.current;
          controller.current = createReadOnlyCodeController(
            monaco,
            element,
            current.code,
            (id) => latest.current.onSelectBlock?.(id),
          );
          controller.current.update(
            current.code,
            current.spans,
            current.selectedBlock,
            current.navigationVersion,
          );
          setReady(true);
        })
        .catch((reason) => {
          if (active) {
            controller.current?.dispose();
            controller.current = null;
            setFailure(
              `代码编辑器无法加载，以下保留纯文本只读内容：${String(reason)}`,
            );
          }
        });
    };
    const observer = new ResizeObserver(initialize);
    observer.observe(element);
    initialize();
    return () => {
      active = false;
      observer.disconnect();
      controller.current?.dispose();
      controller.current = null;
    };
  }, []);
  useEffect(() => {
    controller.current?.update(
      code,
      immutableMap,
      selectedBlock,
      navigationVersion,
    );
  }, [code, immutableMap, selectedBlock, navigationVersion]);
  return (
    <div className="code-view" tabIndex={0} aria-label="只读生成代码">
      {failure && <p role="alert">{failure}</p>}
      {!ready && !failure && <p role="status">正在准备本地只读代码编辑器…</p>}
      <div
        hidden={Boolean(failure)}
        ref={host}
        className="monaco-host"
        aria-label="Monaco 只读代码视图"
      />
      <ol hidden={ready}>
        {code.split("\n").map((text, index) => {
          const line = index + 1;
          const hits = immutableMap.filter(
            (span) => span.startLine <= line && span.endLine >= line,
          );
          const hit = sourceAtLine(immutableMap, line);
          const selected =
            selectedBlock &&
            hits.some((span) => span.origin.blockId === selectedBlock);
          return (
            <li key={line} className={selected ? "code-selected" : undefined}>
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
