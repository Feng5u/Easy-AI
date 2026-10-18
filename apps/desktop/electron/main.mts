import { app, BrowserWindow, ipcMain, protocol, session } from "electron";
import { fileURLToPath } from "node:url";
import { dirname, join, extname } from "node:path";
import { readFile } from "node:fs/promises";
import { startBackend, type Backend } from "./backend.mjs";
import { trustedSender, SECURE_PREFERENCES } from "./security.mjs";

const here = dirname(fileURLToPath(import.meta.url));
protocol.registerSchemesAsPrivileged([
  {
    scheme: "easyai",
    privileges: { standard: true, secure: true, supportFetchAPI: true },
  },
]);
let backend: Backend | undefined;
let quitting = false;
let status = { ready: false, message: "本地服务尚未启动。" };
await app.whenReady();
const assets = join(here, "../dist");
protocol.handle("easyai", async (request) => {
  const url = new URL(request.url);
  // Serve only files enumerated by Vite's output layout, no arbitrary file:// bridge.
  const path = decodeURIComponent(url.pathname);
  if (
    url.host !== "app" ||
    !/^\/(index\.html|assets\/[a-zA-Z0-9_.-]+)$/.test(path)
  )
    return new Response("Forbidden", { status: 403 });
  try {
    const data = await readFile(join(assets, path.slice(1)));
    const mime: Record<string, string> = {
      ".html": "text/html; charset=utf-8",
      ".js": "text/javascript; charset=utf-8",
      ".css": "text/css; charset=utf-8",
    };
    return new Response(data, {
      headers: {
        "Content-Type": mime[extname(path)] ?? "application/octet-stream",
        "X-Content-Type-Options": "nosniff",
      },
    });
  } catch {
    return new Response("Not found", { status: 404 });
  }
});
session.defaultSession.setPermissionRequestHandler(
  (_webContents, _permission, callback) => callback(false),
);
session.defaultSession.setPermissionCheckHandler(() => false);
const window = new BrowserWindow({
  width: 1180,
  height: 780,
  webPreferences: {
    preload: join(here, "preload.cjs"),
    ...SECURE_PREFERENCES,
  },
});
window.webContents.setWindowOpenHandler(() => ({ action: "deny" }));
window.webContents.on("will-navigate", (event) => event.preventDefault());
ipcMain.handle("easyai:status:get", (event) => {
  if (
    event.sender !== window.webContents ||
    !trustedSender(
      event.senderFrame?.url ?? "",
      event.senderFrame === window.webContents.mainFrame,
    )
  )
    throw new Error("IPC sender forbidden");
  return status;
});
const repository = join(here, "../../..");
const python =
  process.platform === "win32"
    ? join(repository, "services/backend/.venv/Scripts/python.exe")
    : join(repository, "services/backend/.venv/bin/python");
try {
  backend = await startBackend(python, join(repository, "services/backend"));
  status = { ready: true, message: "本地服务已就绪。" };
  backend.process.once("exit", () => {
    if (quitting || window.isDestroyed()) return;
    status = { ready: false, message: "本地服务已退出，请重新启动应用。" };
    void window.webContents.reload();
  });
} catch (error) {
  status = {
    ready: false,
    message: error instanceof Error ? error.message : "本地服务无法启动。",
  };
}
await window.loadURL("easyai://app/index.html");
app.on("before-quit", (event) => {
  if (quitting) return;
  event.preventDefault();
  quitting = true;
  void (backend?.stop() ?? Promise.resolve()).finally(() => app.quit());
});
app.on("window-all-closed", () => app.quit());
