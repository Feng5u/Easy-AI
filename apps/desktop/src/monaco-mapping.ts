/** Pure mapping logic shared by the safe fallback and the future CSP-compatible editor. */
import type { CompileResult } from "../electron/bridge.js";

export type CodeSpan = NonNullable<CompileResult["sourceMap"]>[number];
export interface MappedDecoration {
  startLineNumber: number;
  endLineNumber: number;
  kind: "semantic" | "scaffold";
  blockId: string;
}
function valid(span: CodeSpan): boolean {
  return (
    Number.isSafeInteger(span.startLine) &&
    Number.isSafeInteger(span.endLine) &&
    span.startLine >= 1 &&
    span.endLine >= span.startLine
  );
}
/** Never bind a historical RunSource to a mutable caller-owned map. */
export function freezeSourceMap(
  spans: readonly CodeSpan[],
): readonly CodeSpan[] {
  return Object.freeze(
    spans.filter(valid).map((span) =>
      Object.freeze({
        ...span,
        origin: Object.freeze({ ...span.origin }),
      }),
    ),
  );
}
/** Child semantic spans win; scaffold is only a fallback for its own source container. */
export function sourceAtLine(
  spans: readonly CodeSpan[],
  line: number,
): CodeSpan | undefined {
  if (!Number.isSafeInteger(line) || line < 1) return undefined;
  return spans
    .filter(
      (span) => valid(span) && span.startLine <= line && span.endLine >= line,
    )
    .sort(
      (a, b) =>
        Number(a.kind !== "semantic") - Number(b.kind !== "semantic") ||
        a.endLine - a.startLine - (b.endLine - b.startLine) ||
        a.startLine - b.startLine ||
        a.origin.blockId.localeCompare(b.origin.blockId),
    )[0];
}
/** Preserve all disjoint constructor/forward spans; never highlight the intervening code. */
export function decorationsForBlock(
  spans: readonly CodeSpan[],
  blockId: string | null | undefined,
): MappedDecoration[] {
  if (!blockId) return [];
  const seen = new Set<string>();
  return spans
    .filter((span) => valid(span) && span.origin.blockId === blockId)
    .sort((a, b) => a.startLine - b.startLine || a.endLine - b.endLine)
    .flatMap((span) => {
      const key = `${span.startLine}:${span.endLine}:${span.kind}`;
      if (seen.has(key)) return [];
      seen.add(key);
      return [
        {
          startLineNumber: span.startLine,
          endLineNumber: span.endLine,
          kind: span.kind,
          blockId,
        },
      ];
    });
}
export function firstSemanticLine(
  spans: readonly CodeSpan[],
  blockId: string | null | undefined,
): number | undefined {
  const selected = decorationsForBlock(spans, blockId);
  return (
    selected.find((span) => span.kind === "semantic")?.startLineNumber ??
    selected[0]?.startLineNumber
  );
}
