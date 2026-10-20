import type * as Monaco from "monaco-editor/editor/editor.api.js";
import {
  decorationsForBlock,
  firstSemanticLine,
  freezeSourceMap,
  sourceAtLine,
} from "./monaco-mapping.js";
import type { CodeSpan } from "./monaco-mapping.js";

export interface ReadOnlyCodeController {
  update(
    code: string,
    spans: readonly CodeSpan[],
    selectedBlock: string | null | undefined,
    navigationVersion?: number,
  ): void;
  layout(): void;
  dispose(): void;
}
export function createReadOnlyCodeController(
  monaco: typeof Monaco,
  host: HTMLElement,
  initialCode: string,
  onSelectBlock: (id: string) => void,
): ReadOnlyCodeController {
  const model = monaco.editor.createModel(initialCode, "python");
  let editor: Monaco.editor.IStandaloneCodeEditor;
  try {
    editor = monaco.editor.create(host, {
      model,
      readOnly: true,
      domReadOnly: true,
      ariaLabel: "只读生成的 PyTorch 代码",
      theme: "vs-dark",
      fontSize: 12,
      minimap: { enabled: false },
      automaticLayout: false,
      useShadowDOM: false,
      scrollBeyondLastLine: false,
      contextmenu: false,
      folding: false,
      wordBasedSuggestions: "off",
      occurrencesHighlight: "off",
      selectionHighlight: false,
      links: false,
      hover: { enabled: "off" },
      stickyScroll: { enabled: false },
      unicodeHighlight: { ambiguousCharacters: false },
    });
  } catch (error) {
    model.dispose();
    throw error;
  }
  let spans: readonly CodeSpan[] = [];
  let decorations: string[] = [];
  let disposed = false;
  let revealed: string | null | undefined;
  let navigationVersion: number | undefined;
  const mouse = editor.onMouseDown((event) => {
    if (!event.target.position) return;
    const source = sourceAtLine(spans, event.target.position.lineNumber);
    if (source) onSelectBlock(source.origin.blockId);
  });
  return {
    update(code, nextSpans, selectedBlock, nextNavigationVersion) {
      if (disposed) return;
      if (model.getValue() !== code) {
        model.setValue(code);
        revealed = undefined;
      }
      spans = freezeSourceMap(nextSpans);
      const lineCount = model.getLineCount();
      const mapped: Monaco.editor.IModelDeltaDecoration[] = [];
      for (const span of spans) {
        if (span.kind !== "scaffold" || span.endLine > lineCount) continue;
        mapped.push({
          range: new monaco.Range(
            span.startLine,
            1,
            span.endLine,
            model.getLineMaxColumn(span.endLine),
          ),
          options: { inlineClassName: "monaco-source-scaffold" },
        });
      }
      for (const selected of decorationsForBlock(spans, selectedBlock)) {
        if (selected.endLineNumber > lineCount) continue;
        mapped.push({
          range: new monaco.Range(
            selected.startLineNumber,
            1,
            selected.endLineNumber,
            model.getLineMaxColumn(selected.endLineNumber),
          ),
          options: {
            isWholeLine: true,
            className:
              selected.kind === "semantic"
                ? "monaco-source-selected-semantic"
                : "monaco-source-selected-scaffold",
          },
        });
      }
      decorations = editor.deltaDecorations(decorations, mapped);
      if (
        selectedBlock !== revealed ||
        (nextNavigationVersion !== undefined &&
          nextNavigationVersion !== navigationVersion)
      ) {
        const first = firstSemanticLine(spans, selectedBlock);
        if (first !== undefined && first <= lineCount)
          editor.revealLineInCenterIfOutsideViewport(first);
        revealed = selectedBlock;
      }
      if (nextNavigationVersion !== undefined)
        navigationVersion = nextNavigationVersion;
    },
    layout() {
      if (!disposed) editor.layout();
    },
    dispose() {
      if (disposed) return;
      disposed = true;
      mouse.dispose();
      editor.dispose();
      model.dispose();
    },
  };
}
