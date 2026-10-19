import { expect, it, vi } from "vitest";
import * as Blockly from "blockly/core";
import { createRequire } from "node:module";
import { WorkspaceManager } from "../../apps/desktop/src/WorkspaceManager.js";

it("keeps the inspected block while editing outside the canvas, but clears an explicit workspace selection", async () => {
  const require = createRequire(import.meta.url);
  const { JSDOM } = require(
    require.resolve("jsdom", { paths: [require.resolve("blockly/core")] }),
  );
  const dom = new JSDOM("<!doctype html><html><body></body></html>", {
    pretendToBeVisual: true,
  });
  let manager: WorkspaceManager | undefined;
  let failed = false;
  try {
    for (const key of [
      "window",
      "document",
      "Element",
      "HTMLElement",
      "Node",
      "SVGElement",
      "FocusEvent",
      "DOMParser",
      "XMLSerializer",
    ])
      vi.stubGlobal(
        key,
        key === "window"
          ? dom.window
          : key === "document"
            ? dom.window.document
            : dom.window[key],
      );
    vi.stubGlobal(
      "requestAnimationFrame",
      dom.window.requestAnimationFrame.bind(dom.window),
    );
    vi.stubGlobal(
      "cancelAnimationFrame",
      dom.window.cancelAnimationFrame.bind(dom.window),
    );
    const makeHost = () => {
      const host = document.createElement("div");
      document.body.append(host);
      return host;
    };
    const hosts = {
      data: makeHost(),
      model: makeHost(),
      training: makeHost(),
    };
    const onSelect = vi.fn();
    const onChange = vi.fn();
    manager = new WorkspaceManager(hosts, false, {
      onSelect,
      onChange,
      onTabChange: vi.fn(),
      onRefresh: vi.fn(),
    });
    manager.setActive("data");
    const workspace = manager.workspaces.data as Blockly.WorkspaceSvg;
    const block = workspace.newBlock(
      "data.compose",
      "inspected-prep",
    ) as Blockly.BlockSvg;
    // Focus lifecycle needs the actual BlockSvg node, not text measurement or
    // pixel layout (which JSDOM does not implement).
    workspace.getCanvas().appendChild(block.getSvgRoot());
    Blockly.getFocusManager().focusNode(block);
    await vi.waitFor(() => expect(onSelect).toHaveBeenLastCalledWith(block.id));
    expect(document.activeElement).toBe(block.getFocusableElement());
    const input = document.createElement("input");
    input.setAttribute("aria-label", "Inspector name");
    document.body.append(input);
    const focusLossDelivered = new Promise<void>((resolve) => {
      workspace.addChangeListener((event) => {
        if (
          event.type === Blockly.Events.SELECTED &&
          !(event as Blockly.Events.Selected).newElementId
        )
          resolve();
      });
    });
    input.focus();
    await focusLossDelivered;
    expect(document.activeElement).toBe(input);
    expect(Blockly.getFocusManager().getFocusedNode()).toBeNull();
    expect(onSelect).toHaveBeenLastCalledWith(block.id);
    Blockly.Events.fire(
      new Blockly.Events.Click(
        null,
        workspace.id,
        Blockly.Events.ClickTarget.WORKSPACE,
      ),
    );
    await vi.waitFor(() => expect(onSelect).toHaveBeenLastCalledWith(null));
    onChange.mockClear();
    Blockly.Events.fire(
      new Blockly.Events.Click(
        block,
        workspace.id,
        Blockly.Events.ClickTarget.BLOCK,
      ),
    );
    await vi.waitFor(() => expect(onSelect).toHaveBeenLastCalledWith(block.id));
    const zoomDelivered = new Promise<void>((resolve) =>
      workspace.addChangeListener((event) => {
        if (
          event.type === Blockly.Events.CLICK &&
          (event as Blockly.Events.Click).targetType ===
            Blockly.Events.ClickTarget.ZOOM_CONTROLS
        )
          resolve();
      }),
    );
    Blockly.Events.fire(
      new Blockly.Events.Click(
        null,
        workspace.id,
        Blockly.Events.ClickTarget.ZOOM_CONTROLS,
      ),
    );
    await zoomDelivered;
    expect(onSelect).toHaveBeenLastCalledWith(block.id);
    expect(onChange).not.toHaveBeenCalled();
    // Keyboard focus back onto a selected block and then the workspace root
    // remains a genuine deselection, independent of pointer click events.
    Blockly.getFocusManager().focusNode(block);
    await vi.waitFor(() => expect(onSelect).toHaveBeenLastCalledWith(block.id));
    Blockly.getFocusManager().focusNode(workspace);
    await vi.waitFor(() => expect(onSelect).toHaveBeenLastCalledWith(null));
    Blockly.Events.fire(
      new Blockly.Events.Click(
        block,
        workspace.id,
        Blockly.Events.ClickTarget.BLOCK,
      ),
    );
    await vi.waitFor(() => expect(onSelect).toHaveBeenLastCalledWith(block.id));
    manager.remove(block.id);
    await vi.waitFor(() => expect(onSelect).toHaveBeenLastCalledWith(null));
  } catch (error) {
    failed = true;
    throw error;
  } finally {
    try {
      manager?.dispose();
    } catch (error) {
      if (!failed) throw error;
    }
    dom.window.close();
    vi.unstubAllGlobals();
  }
});
