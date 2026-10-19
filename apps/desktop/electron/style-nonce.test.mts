import { it, expect } from "vitest";
import { readFile } from "node:fs/promises";
import { fileURLToPath } from "node:url";
import { adaptStyleNonce } from "../../../scripts/style-nonce-adapter.mjs";
import { renderAppHtml } from "./app-assets.mjs";
it("adds a fresh style-only nonce without script, network or sandbox relaxation", async () => {
  const template = await readFile(
    new URL("../index.html", import.meta.url),
    "utf8",
  );
  const one = renderAppHtml(template),
    two = renderAppHtml(template);
  expect(one).not.toBe(two);
  const nonce = one.match(
    /name="easyai-style-nonce" content="([A-Za-z0-9+/=]+)"/,
  )?.[1];
  expect(nonce).toHaveLength(44);
  expect(one).toContain(`style-src 'self' 'nonce-${nonce}'`);
  expect(one).toContain("script-src 'self'");
  expect(one).toContain("connect-src 'none'");
  expect(one).not.toMatch(/unsafe-inline|unsafe-eval/);
  expect(() => renderAppHtml("broken template")).toThrow();
});
it("adapts only audited style creation sites and fails closed on source drift", async () => {
  for (const [relative, count] of [
    ["../../node_modules/blockly/blockly_compressed.js", 2],
    ["./node_modules/monaco-editor/esm/vs/base/browser/domStylesheets.js", 1],
  ] as const) {
    const path = fileURLToPath(
      new URL(relative, new URL("../", import.meta.url)),
    );
    const source = await readFile(path, "utf8");
    const result = adaptStyleNonce(source, path)!;
    expect(result.split("style.nonce=nonce").length - 1).toBe(count);
    expect(result).not.toContain("unsafe-inline");
    expect(() => adaptStyleNonce(source + "\n", path)).toThrow("drift");
  }
  expect(
    adaptStyleNonce("document.createElement('style')", "/untrusted.js"),
  ).toBeNull();
});
it("adapts only the pinned Monaco view insertion sinks to bounded geometry CSSOM", async () => {
  const path = fileURLToPath(
    new URL(
      "../node_modules/monaco-editor/esm/vs/editor/browser/view/viewLayer.js",
      import.meta.url,
    ),
  );
  const source = await readFile(path, "utf8");
  const result = adaptStyleNonce(source, path)!;
  expect(result).toContain("import { insertMonacoGeometry }");
  expect(result).toContain(
    "insertMonacoGeometry(this._domNode, newLinesHTML, true)",
  );
  expect(result).toContain(
    "insertMonacoGeometry(this._domNode, newLinesHTML, false)",
  );
  expect(result).toContain(
    "insertMonacoGeometry(hugeDomNode, invalidLinesHTML, true)",
  );
  expect(result).not.toContain("this._domNode.innerHTML = newLinesHTML");
  expect(result).not.toContain("insertAdjacentHTML('afterend', newLinesHTML)");
  expect(result).not.toMatch(/unsafe-inline|unsafe-eval/);
  expect(() => adaptStyleNonce(source + "\n", path)).toThrow("drift");
});
