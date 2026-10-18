import { describe, expect, it } from "vitest";
import {
  decorationsForBlock,
  firstSemanticLine,
  freezeSourceMap,
  sourceAtLine,
} from "./monaco-mapping.js";
import type { CodeSpan } from "./monaco-mapping.js";
function span(
  id: string,
  start: number,
  end = start,
  kind: CodeSpan["kind"] = "semantic",
): CodeSpan {
  return {
    file: "train.py",
    startLine: start,
    endLine: end,
    origin: { blockId: id, workspace: "model" },
    kind,
  };
}
describe("source mapping for the read-only editor", () => {
  it("selects the narrowest semantic span before a broader container or scaffold", () => {
    const spans = [
      span("container", 1, 30),
      span("layer", 8, 9),
      span("scaffold", 8, 8, "scaffold"),
    ];
    expect(sourceAtLine(spans, 8)?.origin.blockId).toBe("layer");
    expect(
      sourceAtLine([span("scaffold", 3, 8, "scaffold")], 5)?.origin.blockId,
    ).toBe("scaffold");
    expect(sourceAtLine(spans, 31)).toBeUndefined();
    expect(sourceAtLine(spans, Number.NaN)).toBeUndefined();
  });
  it("retains disjoint constructor/forward spans and their scaffold distinction", () => {
    const spans = [
      span("layer", 20),
      span("layer", 4),
      span("layer", 3, 3, "scaffold"),
      span("other", 10),
      span("layer", 4),
    ];
    expect(
      decorationsForBlock(spans, "layer").map((item) => [
        item.startLineNumber,
        item.endLineNumber,
        item.kind,
      ]),
    ).toEqual([
      [3, 3, "scaffold"],
      [4, 4, "semantic"],
      [20, 20, "semantic"],
    ]);
    expect(firstSemanticLine(spans, "layer")).toBe(4);
    expect(decorationsForBlock(spans, "missing")).toEqual([]);
  });
  it("freezes an independent historical map and never follows current project edits", () => {
    const original = [span("old-block", 4), span("ignored", 0)];
    const frozen = freezeSourceMap(original);
    original[0].origin.blockId = "current-block";
    original[0].startLine = 90;
    expect(sourceAtLine(frozen, 4)?.origin.blockId).toBe("old-block");
    expect(sourceAtLine(frozen, 90)).toBeUndefined();
    expect(Object.isFrozen(frozen)).toBe(true);
    expect(Object.isFrozen(frozen[0].origin)).toBe(true);
    expect(frozen).toHaveLength(1);
  });
});
