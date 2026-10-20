import { describe, expect, it, vi } from "vitest";
import type * as Monaco from "monaco-editor/editor/editor.api.js";
import { createReadOnlyCodeController } from "./monaco-controller.js";
import type { CodeSpan } from "./monaco-mapping.js";

function fakeEditor(fail = false) {
  let source = "one\ntwo\nthree\nfour\nfive";
  let click: ((event: Monaco.editor.IEditorMouseEvent) => void) | undefined;
  const model = {
    getValue: () => source,
    setValue: vi.fn((next: string) => {
      source = next;
    }),
    getLineCount: () => source.split("\n").length,
    getLineMaxColumn: () => 10,
    dispose: vi.fn(),
  };
  const mouse = { dispose: vi.fn() };
  const editor = {
    deltaDecorations: vi.fn(
      (_previous: string[], _next: Monaco.editor.IModelDeltaDecoration[]) => [
        "owned-decoration",
      ],
    ),
    revealLineInCenterIfOutsideViewport: vi.fn(),
    layout: vi.fn(),
    dispose: vi.fn(),
    onMouseDown: vi.fn((callback: typeof click) => {
      click = callback;
      return mouse;
    }),
  };
  class Range {
    constructor(
      public startLineNumber: number,
      public startColumn: number,
      public endLineNumber: number,
      public endColumn: number,
    ) {}
  }
  const create = vi.fn(
    (
      _host: HTMLElement,
      _options: Monaco.editor.IStandaloneEditorConstructionOptions,
    ) => {
      if (fail) throw new Error("editor creation failed");
      return editor;
    },
  );
  const api = {
    editor: { createModel: vi.fn(() => model), create },
    Range,
  } as unknown as typeof Monaco;
  return {
    api,
    model,
    editor,
    mouse,
    create,
    click: (line: number) =>
      click?.({
        target: { position: { lineNumber: line, column: 1 } },
      } as Monaco.editor.IEditorMouseEvent),
  };
}
function span(
  id: string,
  start: number,
  end = start,
  kind: CodeSpan["kind"] = "semantic",
): CodeSpan {
  return {
    startLine: start,
    endLine: end,
    kind,
    origin: { blockId: id, workspace: "model" },
  };
}
describe("read-only Monaco lifecycle adapter", () => {
  it("creates read-only Python, maps clicks to the narrowest source, and freezes the active map", () => {
    const fake = fakeEditor();
    const selected = vi.fn();
    const view = createReadOnlyCodeController(
      fake.api,
      {} as HTMLElement,
      fake.model.getValue(),
      selected,
    );
    const spans = [
      span("parent", 1, 5),
      span("child", 2),
      span("child", 4),
      span("frame", 3, 3, "scaffold"),
    ];
    view.update(fake.model.getValue(), spans, "child");
    spans[1].origin.blockId = "later-edit";
    fake.click(2);
    expect(selected).toHaveBeenCalledWith("child");
    expect(fake.create.mock.calls[0][1]).toMatchObject({
      readOnly: true,
      domReadOnly: true,
      contextmenu: false,
    });
    const decorations = fake.editor.deltaDecorations.mock.calls[0][1];
    expect(
      decorations
        .filter(
          (item) =>
            item.options.className === "monaco-source-selected-semantic",
        )
        .map((item) => item.range.startLineNumber),
    ).toEqual([2, 4]);
    expect(
      decorations.some(
        (item) => item.options.inlineClassName === "monaco-source-scaffold",
      ),
    ).toBe(true);
    expect(
      fake.editor.revealLineInCenterIfOutsideViewport,
    ).toHaveBeenCalledWith(2);
    view.dispose();
  });
  it("reveals repeated explicit navigation without resetting manual scroll during ordinary updates", () => {
    const fake = fakeEditor();
    const view = createReadOnlyCodeController(
      fake.api,
      {} as HTMLElement,
      fake.model.getValue(),
      () => {},
    );
    const code = fake.model.getValue(),
      spans = [span("child", 2)];
    view.update(code, spans, "child", 1);
    view.update(code, spans, "child", 1);
    view.update(code, spans, "child");
    expect(
      fake.editor.revealLineInCenterIfOutsideViewport,
    ).toHaveBeenCalledTimes(1);
    view.update(code, spans, "child", 2);
    expect(
      fake.editor.revealLineInCenterIfOutsideViewport,
    ).toHaveBeenCalledTimes(2);
    expect(
      fake.editor.revealLineInCenterIfOutsideViewport,
    ).toHaveBeenLastCalledWith(2);
    view.update(code, spans, "child");
    view.update(code, spans, "child", 2);
    expect(
      fake.editor.revealLineInCenterIfOutsideViewport,
    ).toHaveBeenCalledTimes(2);
    expect(fake.model.setValue).not.toHaveBeenCalled();
    view.dispose();
  });
  it("updates the owned model and disposes mouse listener/editor/model exactly once", () => {
    const fake = fakeEditor();
    const view = createReadOnlyCodeController(
      fake.api,
      {} as HTMLElement,
      fake.model.getValue(),
      () => {},
    );
    view.update("changed code", [span("new", 1)], "new");
    expect(fake.model.setValue).toHaveBeenCalledWith("changed code");
    view.layout();
    expect(fake.editor.layout).toHaveBeenCalledOnce();
    view.dispose();
    view.dispose();
    view.layout();
    view.update("ignored", [], null);
    expect(fake.mouse.dispose).toHaveBeenCalledOnce();
    expect(fake.editor.dispose).toHaveBeenCalledOnce();
    expect(fake.model.dispose).toHaveBeenCalledOnce();
    expect(fake.editor.layout).toHaveBeenCalledOnce();
    expect(fake.model.setValue).toHaveBeenCalledOnce();
  });
  it("disposes an allocated model if editor creation fails", () => {
    const fake = fakeEditor(true);
    expect(() =>
      createReadOnlyCodeController(
        fake.api,
        {} as HTMLElement,
        "code",
        () => {},
      ),
    ).toThrow("editor creation failed");
    expect(fake.model.dispose).toHaveBeenCalledOnce();
  });
});
