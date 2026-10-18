import { createHash } from "node:crypto";
import { readFileSync } from "node:fs";

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
export function adaptStyleNonce(code, id) {
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
      for (const target of targets)
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
          targets.find((target) =>
            id.replaceAll("\\", "/").endsWith(target.suffix),
          ).suffix,
        );
      return adapted === null ? null : { code: adapted, map: null };
    },
  };
}
