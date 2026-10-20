import { it, expect } from "vitest";
import { createRequire } from "node:module";
import { insertMonacoGeometry } from "./monaco-geometry.js";
const require = createRequire(import.meta.url);
const { JSDOM } = require(
  require.resolve("jsdom", { paths: [require.resolve("blockly/core")] }),
);
it("preserves pinned renderer line/selection geometry through CSSOM without parsing style attributes", () => {
  const dom = new JSDOM(
    "<!doctype html><html><body><div id='target'></div></body></html>",
  );
  try {
    const target = dom.window.document.querySelector("#target");
    const parsed: string[] = [];
    const descriptor = Object.getOwnPropertyDescriptor(
      dom.window.Element.prototype,
      "innerHTML",
    )!;
    Object.defineProperty(dom.window.Element.prototype, "innerHTML", {
      ...descriptor,
      set(value: string) {
        parsed.push(String(value));
        descriptor.set!.call(this, value);
      },
    });
    insertMonacoGeometry(
      target,
      '<div style="top:90px;height:18px;line-height:18px;"><div class="cdr semantic" style="left:0;width:100%;"></div><span title=\'literal style="unchanged"\'>&lt;span style="background:red"&gt;</span></div>',
      true,
    );
    expect(parsed).toHaveLength(1);
    expect(parsed[0]).not.toMatch(/<[^>]*\sstyle="(?:top|left)/);
    const line = target.firstElementChild;
    expect(line.style.top).toBe("90px");
    expect(line.style.height).toBe("18px");
    expect(line.style.lineHeight).toBe("18px");
    expect(target.querySelector(".semantic").style.width).toBe("100%");
    expect(target.querySelector("span").textContent).toBe(
      '<span style="background:red">',
    );
    expect(target.querySelector("span").title).toBe(
      'literal style="unchanged"',
    );
    expect(target.querySelector("[data-easyai-geometry]")).toBeNull();
    insertMonacoGeometry(
      target,
      '<div class="selection" style="top:0px;bottom:1px;left:-2.5px;width:200px;"></div>',
      false,
    );
    expect(target.children).toHaveLength(2);
    expect(target.lastElementChild.style.left).toBe("-2.5px");
    insertMonacoGeometry(
      target,
      '<span style="unicode-bidi:isolate">文字</span>',
      true,
    );
    expect(target.children).toHaveLength(1);
    expect(target.firstElementChild.style.unicodeBidi).toBe("isolate");
  } finally {
    dom.window.close();
  }
});
it("rejects unknown properties, resources and malformed geometry before replacing existing output", () => {
  const dom = new JSDOM("<div id='target'><span>preserved</span></div>");
  try {
    const target = dom.window.document.querySelector("#target");
    for (const style of [
      "background:url(https://example.invalid)",
      "color:red",
      "width:calc(1px + 1px)",
      "width:10px!important",
      "width:-1px",
      "top:1e20px",
      "top:NaNpx",
      "left:2em",
      "position:fixed",
    ]) {
      expect(() =>
        insertMonacoGeometry(target, `<div style="${style}"></div>`, true),
      ).toThrow("MONACO_GEOMETRY");
      expect(target.textContent).toBe("preserved");
    }
    for (const html of [
      "<span style='left:0'></span>",
      '<span data-easyai-geometry="0"></span>',
      '<span style="left:0" style="top:0"></span>',
    ])
      expect(() => insertMonacoGeometry(target, html, true)).toThrow(
        "MONACO_GEOMETRY",
      );
  } finally {
    dom.window.close();
  }
});
