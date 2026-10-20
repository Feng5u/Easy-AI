import { randomBytes } from "node:crypto";
export const STYLE_NONCE_PLACEHOLDER = "EASYAISTYLENONCEPLACEHOLDER";
export function renderAppHtml(template: string): string {
  if (template.split(STYLE_NONCE_PLACEHOLDER).length !== 3)
    throw new Error("Invalid application style nonce template");
  return template.replaceAll(
    STYLE_NONCE_PLACEHOLDER,
    randomBytes(32).toString("base64"),
  );
}
