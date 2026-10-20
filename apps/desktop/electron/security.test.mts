import { describe, it, expect } from "vitest";
import { trustedSender, SECURE_PREFERENCES } from "./security.mjs";
describe("IPC origin boundary", () => {
  it("accepts only our top frame", () => {
    expect(trustedSender("easyai://app/index.html", true)).toBe(true);
  });
  it.each([
    "file:///tmp/index.html",
    "https://app/index.html",
    "easyai://app.evil/index.html",
    "easyai://app/index.html?x=1",
    "garbage",
  ])("rejects %s", (url) => {
    expect(trustedSender(url, true)).toBe(false);
  });
  it("rejects subframes", () => {
    expect(trustedSender("easyai://app/index.html", false)).toBe(false);
  });
});

it("keeps all desktop isolation settings explicit", () => {
  expect(SECURE_PREFERENCES).toEqual({
    nodeIntegration: false,
    contextIsolation: true,
    sandbox: true,
    webSecurity: true,
  });
});
