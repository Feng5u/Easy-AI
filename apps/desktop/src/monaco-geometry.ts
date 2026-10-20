/** Only the pinned Monaco view-layer renderer calls this; not a general HTML API. */
const geometryProperties = new Set([
  "top",
  "bottom",
  "left",
  "right",
  "width",
  "height",
  "line-height",
  "padding-right",
]);
function geometry(raw: string): [string, string][] {
  return raw
    .split(";")
    .filter((part) => part.trim())
    .map((part) => {
      const match = /^\s*([a-z-]+)\s*:\s*([^:;]+?)\s*$/.exec(part);
      if (!match) throw new Error("MONACO_GEOMETRY_INVALID");
      const [, property, value] = match;
      if (
        (property === "unicode-bidi" && value === "isolate") ||
        (property === "position" && value === "absolute")
      )
        return [property, value];
      if (!geometryProperties.has(property))
        throw new Error("MONACO_GEOMETRY_PROPERTY");
      if (property === "width" && value === "100%") return [property, value];
      if (
        !/^-?(?:\d+(?:\.\d+)?|\.\d+)(?:px)?$/.test(value) ||
        !Number.isFinite(Number.parseFloat(value)) ||
        Math.abs(Number.parseFloat(value)) > 1e7 ||
        (!value.endsWith("px") && Number(value) !== 0) ||
        (["width", "height", "line-height", "padding-right"].includes(
          property,
        ) &&
          Number.parseFloat(value) < 0)
      )
        throw new Error("MONACO_GEOMETRY_VALUE");
      return [property, value];
    });
}

export function insertMonacoGeometry(
  target: Element,
  html: string,
  replace: boolean,
): void {
  const styles: [string, string][][] = [];
  // Match opening tags, respecting quoted attributes. Escaped source-code text
  // never enters this branch; no regex is applied to its apparent style strings.
  const markup = String(html).replace(
    /<[a-z][a-z0-9-]*\b(?:[^"'<>]|"[^"]*"|'[^']*')*>/gi,
    (tag) => {
      let styled = false;
      return tag.replace(
        /(\s+)([a-zA-Z_:][\w:.-]*)(?:\s*=\s*("[^"]*"|'[^']*'|[^\s>]+))?/g,
        (
          attribute,
          _space: string,
          name: string,
          value: string | undefined,
        ) => {
          if (name.toLowerCase() === "data-easyai-geometry")
            throw new Error("MONACO_GEOMETRY_MARKER");
          if (name.toLowerCase() !== "style") return attribute;
          if (styled || !value?.startsWith('"'))
            throw new Error("MONACO_GEOMETRY_INVALID");
          styled = true;
          const index = styles.push(geometry(value.slice(1, -1))) - 1;
          return ` data-easyai-geometry="${index}"`;
        },
      );
    },
  );
  const template = target.ownerDocument.createElement("template");
  template.innerHTML = markup;
  // Fail closed on any producer format not covered by the audited transformation.
  if (template.content.querySelector("[style]"))
    throw new Error("MONACO_GEOMETRY_UNTRANSLATED");
  for (const element of template.content.querySelectorAll<
    HTMLElement | SVGElement
  >("[data-easyai-geometry]")) {
    const index = Number(element.getAttribute("data-easyai-geometry"));
    const declarations = styles[index];
    if (!declarations || !element.style)
      throw new Error("MONACO_GEOMETRY_MARKER");
    element.removeAttribute("data-easyai-geometry");
    for (const [property, value] of declarations)
      element.style.setProperty(property, value);
  }
  if (replace) target.replaceChildren(template.content);
  else target.append(template.content);
}
