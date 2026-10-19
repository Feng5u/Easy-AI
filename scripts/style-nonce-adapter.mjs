import { createHash } from "node:crypto";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";

// Audited, pinned creation sites only. A dependency update must re-audit these.
const targets = [
  {
    suffix: "/blockly/blockly_compressed.js",
    sha: "cc761aa447e0d4990e6f7a22a5e173d3a67d7d2775960ef10f80d647e6fe4841",
    needle: 'document.createElement("style")',
    count: 2,
  },
  {
    suffix: "/monaco-editor/esm/vs/base/browser/domStylesheets.js",
    sha: "d75d479eba46e53fe9c230958a9fdafc871218d6879c79f95ba4a2a5aed760c5",
    needle: "document.createElement('style')",
    count: 1,
  },
];
// HTML-generated layout styles need CSSOM, not a nonce on style attributes.
const viewLayer = {
  suffix: "/monaco-editor/esm/vs/editor/browser/view/viewLayer.js",
  sha: "c0ce32a0030014328b6f9045e96a0163ae85bda0317c3db2e4e32c881e54e485",
  replacements: [
    [
      "this._domNode.innerHTML = newLinesHTML;",
      "insertMonacoGeometry(this._domNode, newLinesHTML, true);",
    ],
    [
      "lastChild.insertAdjacentHTML('afterend', newLinesHTML);",
      "insertMonacoGeometry(this._domNode, newLinesHTML, false);",
    ],
    [
      "hugeDomNode.innerHTML = invalidLinesHTML;",
      "insertMonacoGeometry(hugeDomNode, invalidLinesHTML, true);",
    ],
  ],
};
export function adaptStyleNonce(code, id) {
  if (id.replaceAll("\\", "/").endsWith(viewLayer.suffix)) {
    if (
      createHash("sha256").update(code).digest("hex") !== viewLayer.sha ||
      viewLayer.replacements.some(
        ([needle]) => code.split(needle).length - 1 !== 1,
      )
    )
      throw new Error(
        "Monaco view renderer drift; audit pinned dependency before building.",
      );
    let result = code;
    for (const [needle, replacement] of viewLayer.replacements)
      result = result.replace(needle, replacement);
    const helper = fileURLToPath(
      new URL("../apps/desktop/src/monaco-geometry.ts", import.meta.url),
    );
    return `import { insertMonacoGeometry } from ${JSON.stringify(helper)};\n${result}`;
  }
  const target = targets.find((t) =>
    id.replaceAll("\\", "/").endsWith(t.suffix),
  );
  if (!target) return null;
  if (
    createHash("sha256").update(code).digest("hex") !== target.sha ||
    code.split(target.needle).length - 1 !== target.count
  )
    throw new Error(
      "Style creation source drift; audit pinned dependency before building.",
    );
  return code.replaceAll(
    target.needle,
    `(()=>{const style=document.createElement("style");const nonce=document.querySelector('meta[name="easyai-style-nonce"]')?.getAttribute("content");if(!nonce)throw new Error("Missing application style nonce");style.nonce=nonce;return style;})()`,
  );
}
export function styleNoncePlugin() {
  const seen = new Set();
  return {
    name: "easyai-audited-style-nonce",
    enforce: "pre",
    buildStart() {
      seen.clear();
    },
    generateBundle() {
      for (const target of [...targets, viewLayer])
        if (!seen.has(target.suffix))
          throw new Error(
            `Missing audited style creation module: ${target.suffix}`,
          );
      for (const name of [
        "delete-icon.svg",
        "dropdown-arrow.svg",
        "foldout-icon.svg",
        "handclosed.cur",
        "handdelete.cur",
        "handopen.cur",
        "resize-handle.svg",
        "sprites.svg",
      ]) {
        this.emitFile({
          type: "asset",
          fileName: `assets/${name}`,
          source: readFileSync(
            new URL(`../node_modules/blockly/media/${name}`, import.meta.url),
          ),
        });
      }
    },
    transform(code, id) {
      const adapted = adaptStyleNonce(code, id);
      if (adapted !== null)
        seen.add(
          [...targets, viewLayer].find((target) =>
            id.replaceAll("\\", "/").endsWith(target.suffix),
          ).suffix,
        );
      return adapted === null ? null : { code: adapted, map: null };
    },
  };
}
