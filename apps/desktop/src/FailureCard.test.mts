import { expect, it, vi } from "vitest";
import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { FailureCard, operationFailure } from "./FailureCard.js";
import type { FailureStage } from "./FailureCard.js";

it("omits untrusted messages, stack, cause, name and custom string conversion even in details", () => {
  const secrets =
    "alice@private.example /home/alice/private C:\\Users\\Alice password=secret token=key";
  const error = new TypeError(secrets, { cause: new Error(secrets) });
  Object.defineProperty(error, "name", {
    get() {
      throw new Error("must not read name");
    },
  });
  Object.defineProperty(error, "stack", {
    get() {
      throw new Error("must not read stack");
    },
  });
  const onNavigate = vi.fn();
  const markup = renderToStaticMarkup(
    createElement(FailureCard, {
      failure: operationFailure("start", error),
      onNavigate,
    }),
  );
  for (const secret of [
    "private.example",
    "/home/alice",
    "Alice",
    "secret",
    "token=",
  ])
    expect(markup).not.toContain(secret);
  expect(markup).toContain("启动运行未确认");
  expect(markup).toContain("刷新运行历史");
  expect(markup).toContain("TypeError");
  expect(markup).toContain("<details>");
  expect(markup).not.toContain("<details open");
  expect(onNavigate).not.toHaveBeenCalled();
  expect(
    operationFailure("compile", {
      toString() {
        throw new Error("must not stringify");
      },
    }),
  ).toEqual({ stage: "compile", category: "Unknown" });
});
it.each([
  "service",
  "restore",
  "project",
  "import",
  "export",
  "save",
  "selection",
  "compile",
  "start",
  "history",
] as FailureStage[])("renders fixed actionable %s stage", (stage) => {
  const markup = renderToStaticMarkup(
    createElement(FailureCard, {
      failure: operationFailure(stage, "private"),
      onNavigate: vi.fn(),
    }),
  );
  expect(markup).toContain('role="alert"');
  expect(markup).toContain("前往");
  expect(markup).toContain("技术详情");
  expect(markup).not.toContain("private");
});
