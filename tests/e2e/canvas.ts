import { expect, type Locator, type Page } from "@playwright/test";

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
    await this.panel.scrollIntoViewIfNeeded();
    const background = (await this.panel
      .locator(".blocklyMainBackground")
      .first()
      .boundingBox())!;
    const toolbox = (await this.panel
      .locator(".blocklyToolbox")
      .boundingBox())!;
    const left = Math.max(background.x, toolbox.x + toolbox.width);
    return {
      x: left,
      y: background.y,
      width: background.x + background.width - left,
      height: background.height,
    };
  }
  async reveal(element: Locator) {
    // Blockly scrollbars transform the SVG; ordinary DOM scrolling does not pan it.
    for (let attempt = 0; attempt < 4; attempt++) {
      const area = await this.bounds();
      const box = (await element.boundingBox())!;
      const dx =
        box.x < area.x + 12
          ? box.x - area.x - 24
          : box.x + box.width > area.x + area.width - 12
            ? box.x + box.width - area.x - area.width + 24
            : 0;
      const dy =
        box.y < area.y + 12
          ? box.y - area.y - 24
          : box.y + box.height > area.y + area.height - 12
            ? box.y + box.height - area.y - area.height + 24
            : 0;
      if (!dx && !dy) return;
      await this.page.mouse.move(
        area.x + area.width / 2,
        area.y + area.height - 12,
      );
      await this.page.mouse.wheel(dx, dy);
      await this.frame();
    }
    throw new Error(
      "Canvas field was not reachable with actual scrollbar gestures",
    );
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
        this.block(destination.parent)
          .locator(":scope > g.blocklyField")
          .first(),
      );
    }
    const target =
      "parent" in destination
        ? await this.connection(destination.parent, destination.kind)
        : { x: area.x + 50, y: area.y + 40 + destination.row * 85 };
    const before = await this.blocks
      .locator("g[data-id]")
      .evaluateAll((nodes) =>
        nodes.map((node) => node.getAttribute("data-id")),
      );
    await this.panel
      .getByRole("treeitem", { name: category, exact: true })
      .click();
    const escaped = label.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
    const source = this.panel
      .locator(".blocklyFlyout .blocklyBlockCanvas > g[data-id]")
      .filter({ hasText: new RegExp(`^${escaped}`) });
    await expect(source).toHaveCount(1);
    const box = (await source
      .locator(":scope > path.blocklyPath")
      .boundingBox())!;
    const start = { x: box.x + 8, y: box.y + 10 };
    // The previous notch begins 15 workspace units from the left, at y=0.
    const scale = await source
      .locator(":scope > path.blocklyPath")
      .evaluate((path) => Math.abs((path as SVGPathElement).getScreenCTM()!.a));
    await this.page.mouse.move(start.x, start.y);
    await this.page.mouse.down();
    await this.page.mouse.move(start.x + 12, start.y + 4, { steps: 5 });
    await this.page.mouse.move(
      target.x + 8 - ("parent" in destination ? 15 * scale : 0),
      target.y + 10,
      { steps: 20 },
    );
    await this.page.mouse.up();
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
      .locator(":scope > g.blocklyField")
      .filter({ hasText: new RegExp(`^${name}$`) })
      .locator("xpath=following-sibling::*[1]");
  }
  async option(id: string, field: string, value: string) {
    const control = this.field(id, field);
    await this.reveal(control);
    await control.click();
    await this.page.getByRole("option", { name: value, exact: true }).click();
    await expect(control).toContainText(value);
  }
  async number(id: string, field: string, value: string) {
    const control = this.field(id, field);
    await this.reveal(control);
    await control.click();
    const input = this.page.locator("input.blocklyHtmlInput");
    await expect(input).toBeVisible();
    await input.fill(value);
    await input.press("Enter");
    await expect(control).toContainText(value);
  }
  async register(id: string, name: string) {
    const header = this.block(id).locator(":scope > g.blocklyField").first();
    await this.reveal(header);
    await header.click();
    const inspector = this.page.getByRole("complementary", {
      name: "对象注册与引用",
    });
    await expect(inspector.locator(":scope > small")).toHaveText(id);
    const input = inspector.getByRole("textbox", {
      name: "用于生成代码的名称",
    });
    await input.fill(name);
    await input.press("Enter");
    await inspector.getByRole("checkbox", { name: "供本项目引用" }).check();
    await expect(
      inspector.getByRole("button", { name: new RegExp(`^${name}`) }),
    ).toBeVisible();
  }
}
