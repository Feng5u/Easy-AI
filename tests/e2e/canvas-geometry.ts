/** Read-only measurement, serialized unchanged into the actual renderer. */
export function inspectCanvasGeometry(panel: Element) {
  const view = panel.ownerDocument.defaultView!;
  const rect = (element: Element | null) => {
    if (!element) return null;
    const box = element.getBoundingClientRect();
    return {
      x: box.x,
      y: box.y,
      width: box.width,
      height: box.height,
      left: box.left,
      right: box.right,
      top: box.top,
      bottom: box.bottom,
    };
  };
  const background = panel.querySelector(".blocklyMainBackground");
  const svg = background?.closest("svg") ?? null;
  const toolbox = panel.querySelector(".blocklyToolbox");
  const scrollbar = (axis: string) => {
    const element = panel.querySelector(
      `.injectionDiv > .blocklyScrollbar${axis}`,
    );
    return {
      viewport: rect(element),
      handle: rect(element?.querySelector(".blocklyScrollbarHandle") ?? null),
      transform: (element as SVGElement | null)?.style.transform ?? null,
      display: element ? view.getComputedStyle(element).display : null,
    };
  };
  const geometry = {
    viewport: { width: view.innerWidth, height: view.innerHeight },
    panel: rect(panel),
    svg: rect(svg),
    background: rect(background),
    toolbox: rect(toolbox),
    flyout: rect(panel.querySelector(".blocklyFlyout")),
    horizontal: scrollbar("Horizontal"),
    vertical: scrollbar("Vertical"),
  };
  if (!geometry.svg || !geometry.background || !geometry.toolbox)
    return { geometry, area: { x: 0, y: 0, width: 0, height: 0 } };
  // An SVG scrollbar viewport is not a painted occlusion rectangle. Its
  // background has pointer-events:none and its handle is only part of it.
  // Use the real main SVG viewport; gestures additionally hit-test the actual
  // workspace, and all field clicks retain Playwright's receives-events gate.
  const left = Math.max(
    0,
    geometry.svg.left,
    geometry.background.left,
    geometry.toolbox.right,
  );
  const top = Math.max(0, geometry.svg.top, geometry.background.top);
  const right = Math.min(
    view.innerWidth,
    geometry.svg.right,
    geometry.background.right,
  );
  const bottom = Math.min(
    view.innerHeight,
    geometry.svg.bottom,
    geometry.background.bottom,
  );
  return {
    geometry,
    area: { x: left, y: top, width: right - left, height: bottom - top },
  };
}

/** A physical destination must actually belong to this main SVG workspace. */
export function mainWorkspaceOwnsPoint(
  panel: Element,
  point: { x: number; y: number },
) {
  const workspace = panel.querySelector(
    ".blocklyMainBackground",
  )?.parentElement;
  const hit = panel.ownerDocument.elementFromPoint(point.x, point.y);
  return Boolean(hit && workspace?.contains(hit));
}
