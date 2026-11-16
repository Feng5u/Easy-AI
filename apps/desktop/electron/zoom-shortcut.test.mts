import { expect, it } from "vitest";
import { zoomShortcut } from "./zoom-shortcut.mjs";

it.each([
  ["=", "Equal", 1],
  ["+", "Equal", 1],
  ["+", "NumpadAdd", 1],
  ["-", "Minus", -1],
  ["-", "NumpadSubtract", -1],
  ["0", "Digit0", 0],
  ["0", "Numpad0", 0],
] as const)("recognizes the %s / %s zoom key", (key, code, direction) => {
  expect(zoomShortcut(key, code, true, false)).toBe(direction);
  expect(zoomShortcut(key, code, false, false)).toBeNull();
  expect(zoomShortcut(key, code, true, true)).toBeNull();
});

it("leaves unrelated shortcuts alone", () => {
  expect(zoomShortcut("c", "KeyC", true, false)).toBeNull();
  expect(zoomShortcut("z", "KeyZ", true, false)).toBeNull();
});
