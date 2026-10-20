import {
  fieldLabels,
  adjacentField,
  fieldLabelPattern,
  blockLabelPrefix,
} from "./canvas-fields.js";
import { test, expect, type Locator, type Page } from "@playwright/test";
import {
  inspectCanvasGeometry,
  mainWorkspacePointer,
  fieldHitPoint,
  mainWorkspaceOwnsPoint,
} from "./canvas-geometry.js";

const sessions = new WeakMap<object, AbortController>();
function interactionSignal() {
  const info = test.info();
  let session = sessions.get(info);
  if (!session) sessions.set(info, (session = new AbortController()));
  session.signal.throwIfAborted();
  return session;
}

export async function interaction<T>(
  label: string,
  body: (signal: AbortSignal) => Promise<T>,
) {
  const session = interactionSignal();
  console.info(`EASYAI_TOOLBOX_ACTION BEGIN ${label}`);
  try {
    const result = await test.step(label, () => body(session.signal), {
      timeout: 15000,
    });
    console.info(`EASYAI_TOOLBOX_ACTION PASS ${label}`);
    return result;
  } catch (error) {
    // A timeout cannot cancel an already dispatched CDP operation. Stop any
    // subsequent gestures when it returns; shutdown must still confirm exit.
    session.abort(error);
    console.error(`EASYAI_TOOLBOX_ACTION FAIL ${label}`);
    throw error;
  }
}

export class Canvas {
  readonly panel: Locator;
  readonly blocks: Locator;
  constructor(
    readonly page: Page,
    tab: string,
  ) {
    this.panel = page.getByRole("tabpanel", { name: tab, exact: true });
    this.blocks = this.panel
      .locator(".blocklySvg .blocklyWorkspace > .blocklyBlockCanvas")
      .first();
  }
  block(id: string) {
    return this.blocks.locator(`g[data-id=${JSON.stringify(id)}]`);
  }
  async frame() {
    await this.page.evaluate(
      () =>
        new Promise<void>((resolve) =>
          requestAnimationFrame(() => requestAnimationFrame(() => resolve())),
        ),
    );
  }
  async bounds() {
    interactionSignal();
    await this.panel.scrollIntoViewIfNeeded();
    await this.frame();
    const snapshot = await this.panel.evaluate(inspectCanvasGeometry);
    console.info("EASYAI_TOOLBOX_CANVAS_GEOMETRY", JSON.stringify(snapshot));
    if (snapshot.area.width < 48 || snapshot.area.height < 48)
      throw new Error("Canvas has no usable visible interaction area");
    return snapshot.area;
  }

  async reveal(element: Locator, allowBlock = false) {
    // Blockly scrollbars transform the SVG; ordinary DOM scrolling does not pan it.
    for (let attempt = 0; attempt <= 4; attempt++) {
      const area = await this.bounds();
      const box = (await element.boundingBox())!;
      let dx =
        box.x < area.x + 12
          ? box.x - area.x - 24
          : box.x + box.width > area.x + area.width - 12
            ? box.x + box.width - area.x - area.width + 24
            : 0;
      let dy =
        box.y < area.y + 12
          ? box.y - area.y - 24
          : box.y + box.height > area.y + area.height - 12
            ? box.y + box.height - area.y - area.height + 24
            : 0;
      const hit = await element.evaluate(fieldHitPoint, { area, allowBlock });
      if (!dx && !dy && hit.point) return hit.point;
      console.info(
        "EASYAI_TOOLBOX_REVEAL_GEOMETRY",
        JSON.stringify({ attempt, area, box, dx, dy, hit }),
      );
      if (attempt === 4) break;
      // Scrollbars are siblings of the main SVG; their wheel events never
      // reach the workspace listener. Hit-test a visible point inside it.
      const pointer = await this.panel.evaluate(mainWorkspacePointer, area);
      if (!hit.point) {
        // Viewport inclusion alone is insufficient: fixed zoom controls (or
        // another overlay) may cover the field. Pan its centre to a point
        // actually owned by the main workspace, leaving all controls intact.
        dx = box.x + box.width / 2 - pointer.x;
        dy = box.y + box.height / 2 - pointer.y;
      }
      interactionSignal();
      await this.page.mouse.move(pointer.x, pointer.y);
      interactionSignal();
      await this.page.mouse.wheel(dx, dy);
      await this.frame();
    }
    throw new Error(
      "Canvas field was not reachable with actual scrollbar gestures",
    );
  }
  async sourceVisible(id: string) {
    // Observation only: do not pan/reveal here, since explicit navigation must
    // restore visibility by itself, including the document viewport.
    await expect(this.block(id)).toBeInViewport();
    await expect
      .poll(async () => {
        const { area } = await this.panel.evaluate(inspectCanvasGeometry);
        const box = await this.block(id)
          .locator(":scope > path.blocklyPath")
          .boundingBox();
        return Boolean(
          box &&
          area.width >= 48 &&
          area.height >= 48 &&
          box.x >= area.x &&
          box.y >= area.y &&
          box.x + box.width <= area.x + area.width &&
          box.y + box.height <= area.y + area.height,
        );
      })
      .toBe(true);
  }
  async panSourceOut(id: string, source: Locator) {
    // Blockly deliberately retains half a viewport of padded content. A wide
    // block may remain partly painted at the scroll limit; its actual title
    // must leave the canvas, and relocation below must restore the entire path.
    const header = this.block(id).locator(fieldLabels).first();
    for (let attempt = 0; attempt <= 4; attempt++) {
      const area = await this.bounds();
      const box = (await header.boundingBox())!;
      const outside =
        box.x + box.width <= area.x ||
        box.x >= area.x + area.width ||
        box.y + box.height <= area.y ||
        box.y >= area.y + area.height;
      console.info(
        "EASYAI_TOOLBOX_SOURCE_GEOMETRY",
        JSON.stringify({
          id,
          attempt,
          area,
          header: box,
          outside,
          block: await this.block(id).boundingBox(),
        }),
      );
      if (outside) {
        await source.scrollIntoViewIfNeeded();
        await expect(source).toBeInViewport();
        await expect(header).not.toBeInViewport();
        return;
      }
      if (attempt === 4) break;
      const pointer = await this.panel.evaluate(mainWorkspacePointer, area);
      await interaction(
        "pan the selected source title outside the canvas",
        async (signal) => {
          await this.page.mouse.move(pointer.x, pointer.y);
          signal.throwIfAborted();
          await this.page.mouse.wheel(area.width * 2 + box.width, 0);
          await this.frame();
        },
      );
    }
    throw new Error(
      "The selected source title did not leave the actual workspace viewport",
    );
  }
  async clickField(
    element: Locator,
    label: string,
    receiver: Locator = element,
  ) {
    const point = await this.reveal(element, receiver !== element);
    await interaction(label, async (signal) => {
      const box = (await receiver.boundingBox())!;
      signal.throwIfAborted();
      await receiver.click({
        position: { x: point.x - box.x, y: point.y - box.y },
      });
    });
  }
  async connection(id: string, kind: "input" | "next") {
    // Read the actual pinned Geras notch path. A detached SVG path measures its
    // prefix only; this never mutates Blockly, loads a graph or connects blocks.
    return this.block(id)
      .locator(":scope > path.blocklyPath")
      .evaluate((element, which) => {
        const path = element as SVGPathElement;
        const d = path.getAttribute("d")!;
        const notches = [...d.matchAll(/l\s*-6,4\s+-3,0\s+-6,-4/g)];
        const notch = which === "input" ? notches[0] : notches.at(-1);
        if (!notch)
          throw new Error("Rendered Geras connection notch not found");
        const probe = document.createElementNS(
          "http://www.w3.org/2000/svg",
          "path",
        );
        probe.setAttribute("d", d.slice(0, notch.index));
        const point = probe.getPointAtLength(probe.getTotalLength());
        const screen = new DOMPoint(point.x - 15, point.y).matrixTransform(
          path.getScreenCTM()!,
        );
        return { x: screen.x, y: screen.y };
      }, kind);
  }
  async drag(
    label: string,
    category: string,
    destination: { row: number } | { parent: string; kind: "input" | "next" },
  ) {
    const area = await this.bounds();
    if ("parent" in destination) {
      // Selecting a block through the inspector is not needed: pan the actual
      // canvas to its header before measuring the physical connection.
      await this.reveal(
        this.block(destination.parent).locator(fieldLabels).first(),
        true,
      );
    }
    const target =
      "parent" in destination
        ? await this.connection(destination.parent, destination.kind)
        : { x: area.x + 50, y: area.y + 40 + destination.row * 85 };
    expect(
      await this.panel.evaluate(mainWorkspaceOwnsPoint, target),
      "The measured drop destination must hit the actual main workspace before opening the flyout",
    ).toBe(true);
    const before = await this.blocks
      .locator("g[data-id]")
      .evaluateAll((nodes) =>
        nodes.map((node) => node.getAttribute("data-id")),
      );
    await interaction(`toolbox category ${category} for ${label}`, () =>
      this.panel.getByRole("treeitem", { name: category, exact: true }).click(),
    );
    const source = this.panel
      .locator(".blocklyFlyout .blocklyBlockCanvas > g[data-id]")
      .filter({ hasText: blockLabelPrefix(label) });
    await expect(source).toHaveCount(1);
    await expect(source).toBeVisible();
    const box = (await source
      .locator(":scope > path.blocklyPath")
      .boundingBox())!;
    const start = { x: box.x + 8, y: box.y + 10 };
    // The previous notch begins 15 workspace units from the left, at y=0.
    const scale = await source
      .locator(":scope > path.blocklyPath")
      .evaluate((path) => Math.abs((path as SVGPathElement).getScreenCTM()!.a));
    console.info(
      "EASYAI_TOOLBOX_DRAG_GEOMETRY",
      JSON.stringify({
        label,
        area,
        target,
        source: box,
        scale,
        existingBlocks: before.length,
      }),
    );
    await interaction(`physical drag ${label}`, async (signal) => {
      await this.page.mouse.move(start.x, start.y);
      signal.throwIfAborted();
      await this.page.mouse.down();
      try {
        signal.throwIfAborted();
        await this.page.mouse.move(start.x + 12, start.y + 4, { steps: 5 });
        signal.throwIfAborted();
        await this.page.mouse.move(
          target.x + 8 - ("parent" in destination ? 15 * scale : 0),
          target.y + 10,
          { steps: 20 },
        );
      } finally {
        await this.page.mouse.up();
      }
    });
    await this.frame();
    await expect(this.blocks.locator(".blocklyInsertionMarker")).toHaveCount(0);
    await expect(this.blocks.locator("g[data-id]")).toHaveCount(
      before.length + 1,
    );
    const after = await this.blocks
      .locator("g[data-id]")
      .evaluateAll((nodes) =>
        nodes.map((node) => node.getAttribute("data-id")),
      );
    const id = after.find((item) => !before.includes(item))!;
    if ("parent" in destination)
      await expect(
        this.block(destination.parent).locator(
          `g[data-id=${JSON.stringify(id)}]`,
        ),
      ).toHaveCount(1);
    return id;
  }
  field(id: string, name: string) {
    return this.block(id)
      .locator(fieldLabels)
      .filter({ hasText: fieldLabelPattern(name) })
      .locator(adjacentField);
  }
  async option(id: string, field: string, value: string) {
    const control = this.field(id, field);
    await this.clickField(control, `open reference or enum ${field}`);
    await interaction(`choose reference or enum ${field}`, () =>
      this.page.getByRole("option", { name: value, exact: true }).click(),
    );
    await expect(control).toContainText(value);
  }
  async number(id: string, field: string, value: string) {
    const control = this.field(id, field);
    await this.clickField(control, `open number ${field}`);
    const input = this.page.locator("input.blocklyHtmlInput");
    await expect(input).toBeVisible();
    await interaction(`edit number ${field}`, async (signal) => {
      await input.fill(value);
      signal.throwIfAborted();
      await input.press("Enter");
    });
    await expect(control).toContainText(value);
  }
  async register(id: string, name: string) {
    const header = this.block(id).locator(fieldLabels).first();
    await this.clickField(
      header,
      `select object for registration ${name}`,
      this.block(id),
    );
    const inspector = this.page.getByRole("complementary", {
      name: "对象注册与引用",
    });
    await expect(
      inspector.getByLabel("所选积木 ID", { exact: true }),
    ).toHaveText(id);
    const input = inspector.getByRole("textbox", {
      name: "用于生成代码的名称",
    });
    await interaction(`rename object ${name}`, async (signal) => {
      await input.fill(name);
      signal.throwIfAborted();
      await input.press("Enter");
    });
    await expect(this.field(id, "NAME")).toContainText(name);
    await interaction(`register object ${name}`, () =>
      inspector.getByRole("checkbox", { name: "供本项目引用" }).check(),
    );
    await expect(
      inspector.getByLabel("所选积木 ID", { exact: true }),
    ).toHaveText(id);
    await expect(
      inspector.getByRole("button", { name: new RegExp(`^${name}`) }),
    ).toBeVisible();
  }
}
