import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { act, createElement } from "react";
import type { Root } from "react-dom/client";
import { createRequire } from "node:module";
import { readFileSync } from "node:fs";
import { TutorialPanel, LocalMarkdown } from "./TutorialPanel.js";
import { tutorials, tutorialForBlock, tutorialTargets } from "./tutorials.js";
import manifest from "../../../packages/block-library/manifest.json";
import type { CompileResult, ProjectDocument } from "../electron/bridge.js";
const require = createRequire(import.meta.url),
  { JSDOM } = require(
    require.resolve("jsdom", { paths: [require.resolve("blockly/core")] }),
  );
let dom: InstanceType<typeof JSDOM>,
  root: Root | undefined,
  container: HTMLDivElement;
const fixture = () =>
  JSON.parse(
    readFileSync(
      new URL(
        "../../../packages/contracts/fixtures/mnist.json",
        import.meta.url,
      ),
      "utf8",
    ),
  ) as ProjectDocument;
const code = readFileSync(
  new URL(
    "../../../services/backend/tests/fixtures/golden/mnist.py.txt",
    import.meta.url,
  ),
  "utf8",
);
const spans = JSON.parse(
  readFileSync(
    new URL(
      "../../../services/backend/tests/fixtures/golden/mnist-source-map.json",
      import.meta.url,
    ),
    "utf8",
  ),
) as CompileResult["sourceMap"];
async function mount(element: ReturnType<typeof createElement>) {
  const { createRoot } = await import("react-dom/client");
  root ??= createRoot(container);
  await act(async () => {
    root!.render(element);
  });
}
async function click(label: string) {
  await act(async () => {
    const node = [...container.querySelectorAll("button")].find(
      (item) =>
        item.textContent === label || item.getAttribute("aria-label") === label,
    );
    if (!node) throw Error("missing " + label);
    node.click();
  });
}
async function weight(value: string) {
  const input =
    container.querySelector<HTMLInputElement>(".kernel-grid input")!;
  await act(async () => {
    Object.getOwnPropertyDescriptor(
      dom.window.HTMLInputElement.prototype,
      "value",
    )!.set!.call(input, value);
    input.dispatchEvent(new dom.window.Event("input", { bubbles: true }));
  });
}
beforeEach(() => {
  dom = new JSDOM("<!doctype html><html><body></body></html>", {
    url: "https://local-tutorial.test",
  });
  for (const key of [
    "window",
    "document",
    "navigator",
    "HTMLElement",
    "Node",
    "HTMLInputElement",
  ])
    vi.stubGlobal(
      key,
      key === "window"
        ? dom.window
        : key === "document"
          ? dom.window.document
          : dom.window[key],
    );
  vi.stubGlobal("IS_REACT_ACT_ENVIRONMENT", true);
  vi.stubGlobal(
    "ResizeObserver",
    class {
      observe() {}
      disconnect() {}
    },
  );
  container = document.createElement("div");
  document.body.append(container);
});
afterEach(async () => {
  if (root) await act(async () => root!.unmount());
  root = undefined;
  vi.unstubAllGlobals();
  dom.window.close();
});
function props() {
  const project = fixture();
  return {
    topicId: "convolution" as const,
    onTopic: vi.fn(),
    project,
    compilation: {
      revision: project.revision,
      programHash: "a".repeat(64),
      diagnostics: [],
      runnable: true,
      code,
      sourceMap: spans,
    } as CompileResult,
    dirty: false,
    canCreateExample: true,
    onExample: vi.fn(),
    onLocate: vi.fn(),
  };
}
it("bundles seven local Markdown topics and every manifest help key has a relevant lesson", () => {
  expect(tutorials).toHaveLength(7);
  for (const topic of tutorials) {
    expect(topic.markdown).toMatch(/^# /);
    expect(topic.markdown.length).toBeGreaterThan(150);
    expect(topic.relevantBlockTypes.length).toBeGreaterThan(0);
  }
  for (const spec of manifest.blocks)
    expect(tutorialForBlock(spec.id)?.relevantBlockTypes).toContain(spec.id);
  expect(tutorialForBlock("javascript:private")).toBeUndefined();
});
it("local convolution recomputes products, sums and output when moving or editing the kernel", async () => {
  const p = props(),
    before = JSON.stringify(p.project);
  await mount(createElement(TutorialPanel, p));
  expect(container.querySelector("output")?.textContent).toBe("窗口求和：63");
  expect(container.querySelectorAll(".convolution-window")).toHaveLength(9);
  await click("下一个窗口");
  expect(container.querySelector("output")?.textContent).toBe("窗口求和：72");
  expect(
    container.querySelector('[aria-label="九项乘积"]')?.textContent,
  ).toContain("2 × 1 = 2");
  await weight("2");
  expect(container.querySelector("output")?.textContent).toBe("窗口求和：74");
  await click("输出第 3 行第 3 列");
  expect(container.querySelector("output")?.textContent).toBe("窗口求和：184");
  await weight("");
  expect(container.querySelector("output")).toBeNull();
  expect(container.querySelector('[role="alert"]')?.textContent).toContain(
    "有限数值",
  );
  await click("重置卷积演示");
  expect(container.querySelector("output")?.textContent).toBe("窗口求和：63");
  expect(JSON.stringify(p.project)).toBe(before);
  expect(p.onExample).not.toHaveBeenCalled();
  expect(p.onLocate).not.toHaveBeenCalled();
});
it("links fixture block and golden Python spans without modifying project or inventing code", async () => {
  const p = props(),
    before = JSON.stringify(p.project);
  await mount(createElement(TutorialPanel, p));
  const target = tutorialTargets(p.project, tutorials[2].relevantBlockTypes)[0];
  expect(target.type).toBe("model.conv2d");
  await click("定位关联积木");
  expect(p.onLocate).toHaveBeenCalledExactlyOnceWith(target);
  await click("显示对应代码");
  expect(
    container.querySelector(
      '[aria-label="教程关联的只读生成代码"] .code-selected',
    )?.textContent,
  ).toContain("nn.Conv2d");
  expect(JSON.stringify(p.project)).toBe(before);
  expect(p.onExample).not.toHaveBeenCalled();
});
it.each(["dirty", "stale", "missing"])(
  "%s code is unavailable while local computation remains usable",
  async (variant) => {
    const p = props();
    if (variant === "dirty") p.dirty = true;
    if (variant === "stale") p.compilation.revision += 1;
    if (variant === "missing") p.compilation.sourceMap = [];
    await mount(createElement(TutorialPanel, p));
    const button = [...container.querySelectorAll("button")].find(
      (item) => item.textContent === "显示对应代码",
    )!;
    expect(button.disabled).toBe(true);
    expect(container.querySelector("output")?.textContent).toContain("63");
  },
);
it("unknown or duplicate snapshot identity cannot become a tutorial target", () => {
  const p = fixture(),
    before = JSON.stringify(p);
  const model = p.workspaces.model.blocks.blocks![0];
  p.workspaces.data.blocks.blocks!.push({ ...structuredClone(model) });
  expect(tutorialTargets(p, tutorials[2].relevantBlockTypes)).toEqual([]);
  expect(before).not.toBe(JSON.stringify(p));
});
it("Markdown HTML and unsafe links are displayed as text, never executed", async () => {
  await mount(
    createElement(LocalMarkdown, {
      text: "# Local\n\n<img src=x onerror=alert(1)>\n\n[unsafe](javascript:alert(1))",
    }),
  );
  expect(container.querySelector("img")).toBeNull();
  expect(container.querySelector("a")).toBeNull();
  expect(container.textContent).toContain("<img");
});

it("disabled chain heads skip only themselves and inputs, retaining enabled next blocks", () => {
  const project = fixture();
  const model = project.workspaces.model.blocks.blocks![0] as {
    inputs: {
      body: {
        block: {
          id: string;
          disabledReasons?: string[];
          next: { block: { id: string } };
        };
      };
    };
  };
  const first = model.inputs.body.block;
  const nextId = first.next.block.id;
  expect(
    tutorialTargets(project, tutorials[2].relevantBlockTypes).some(
      (item) => item.id === nextId,
    ),
  ).toBe(true);
  first.disabledReasons = ["MANUALLY_DISABLED"];
  const targets = tutorialTargets(project, tutorials[2].relevantBlockTypes);
  expect(targets.some((item) => item.id === first.id)).toBe(false);
  expect(targets.some((item) => item.id === nextId)).toBe(true);
});
it("environment lesson distinguishes auto fallback from explicit device failure", () => {
  const text = tutorials.find((item) => item.id === "environments")!.markdown;
  expect(text).toContain("自动模式（auto）");
  expect(text).toContain("显式指定");
  expect(text).toContain("阻断运行，不会静默回退");
});
