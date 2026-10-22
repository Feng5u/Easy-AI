export const APP_ORIGIN = "easyai://app";
export function trustedSender(url: string, isMainFrame: boolean): boolean {
  try {
    const parsed = new URL(url);
    return (
      isMainFrame &&
      parsed.protocol === "easyai:" &&
      parsed.host === "app" &&
      parsed.pathname === "/index.html" &&
      !parsed.search &&
      !parsed.hash
    );
  } catch {
    return false;
  }
}

export const SECURE_PREFERENCES = Object.freeze({
  nodeIntegration: false,
  contextIsolation: true,
  sandbox: true,
  webSecurity: true,
});
