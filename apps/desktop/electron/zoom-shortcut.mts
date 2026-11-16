/** Shared by native accelerator routing and the Blockly keyboard handler. */
export function zoomShortcut(
  key: string,
  code: string,
  primaryModifier: boolean,
  alt: boolean,
): -1 | 0 | 1 | null {
  if (!primaryModifier || alt) return null;
  if (key === "+" || key === "=" || code === "NumpadAdd") return 1;
  if (key === "-" || code === "NumpadSubtract") return -1;
  if (key === "0" || code === "Numpad0") return 0;
  return null;
}
