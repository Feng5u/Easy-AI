/** Pinned Blockly 13.4 DOM: static labels and editable controls are distinct. */
export const fieldLabels = ":scope > g.blocklyLabelField";
export const adjacentField =
  "xpath=following-sibling::*[1][contains(concat(' ', normalize-space(@class), ' '), ' blocklyField ')]";
export function fieldLabelPattern(name: string) {
  return new RegExp(`^${name.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")}$`);
}

/** Blockly SVG display text replaces spaces with NBSP; match both forms. */
export function blockLabelPrefix(text: string) {
  return new RegExp(
    "^" +
      text
        .split(/\s+/)
        .map((part) => part.replace(/[.*+?^${}()|[\]\\]/g, "\\$&"))
        .join("\\s+"),
  );
}
