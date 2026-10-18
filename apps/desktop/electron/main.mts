import {
  app,
  BrowserWindow,
  ipcMain,
  protocol,
  session,
  dialog,
  type IpcMainInvokeEvent,
} from "electron";
import { setTimeout as delay } from "node:timers/promises";
import { renderAppHtml } from "./app-assets.mjs";
import { MainWorkflow, WORKFLOW_CHANNELS } from "./workflow.mjs";
import { fileURLToPath } from "node:url";
import { dirname, join, extname } from "node:path";
import { readFile } from "node:fs/promises";
import { startBackend, type Backend } from "./backend.mjs";
import { trustedSender, SECURE_PREFERENCES } from "./security.mjs";
import { backendLocation } from "./backend-location.mjs";

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
let draftDirty = false;
if (!app.requestSingleInstanceLock()) app.exit(0);
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
      ".ttf": "font/ttf",
      ".woff2": "font/woff2",
      ".png": "image/png",
      ".svg": "image/svg+xml",
      ".cur": "image/x-icon",
    };
    return new Response(
      path === "/index.html" ? renderAppHtml(data.toString("utf8")) : data,
      {
        headers: {
          "Content-Type": mime[extname(path)] ?? "application/octet-stream",
          "X-Content-Type-Options": "nosniff",
        },
      },
    );
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
function authorizeSender(event: IpcMainInvokeEvent): void {
  if (
    event.sender !== window.webContents ||
    !trustedSender(
      event.senderFrame?.url ?? "",
      event.senderFrame === window.webContents.mainFrame,
    )
  )
    throw new Error("IPC sender forbidden");
}
ipcMain.handle("easyai:status:get", (event) => {
  authorizeSender(event);
  return status;
});
ipcMain.handle("easyai:projects:dirty", (event, ...args: unknown[]) => {
  authorizeSender(event);
  if (args.length !== 1 || typeof args[0] !== "boolean")
    throw new Error("草稿状态无效。");
  draftDirty = args[0];
});
const workflow = new MainWorkflow(
  () => backend,
  async (kind) => {
    const titles = {
      project: "选择项目目录",
      python: "选择已有训练环境的 Python",
      data: "选择已准备的数据目录（不会下载）",
    };
    const selected = await dialog.showOpenDialog(window, {
      title: titles[kind],
      properties: kind === "python" ? ["openFile"] : ["openDirectory"],
    });
    return selected.canceled ? null : (selected.filePaths[0] ?? null);
  },
  (message) => {
    if (!window.isDestroyed())
      window.webContents.send("easyai:runs:message", message);
  },
  {
    async installSources() {
      const selected = await dialog.showOpenDialog(window, {
        title: "选择可信操作者准备的本地离线来源清单（先核验，不安装）",
        properties: ["openFile"],
        filters: [{ name: "Easy-AI 离线来源清单", extensions: ["json"] }],
      });
      return selected.canceled ? null : (selected.filePaths[0] ?? null);
    },
    async privateKey() {
      const selected = await dialog.showOpenDialog(window, {
        title: "选择本次认证使用的 SSH 私钥（不复制、不记住）",
        properties: ["openFile"],
      });
      return selected.canceled ? null : (selected.filePaths[0] ?? null);
    },
    async importProject() {
      const source = await dialog.showOpenDialog(window, {
        title: "选择可移植工程 JSON",
        properties: ["openFile"],
        filters: [{ name: "Easy-AI 工程", extensions: ["json"] }],
      });
      if (source.canceled || !source.filePaths[0]) return null;
      const destination = await dialog.showOpenDialog(window, {
        title: "选择导入目标目录（不覆盖已有工程）",
        properties: ["openDirectory"],
      });
      return destination.canceled || !destination.filePaths[0]
        ? null
        : {
            sourcePath: source.filePaths[0],
            destinationPath: destination.filePaths[0],
          };
    },
    async exportDiagnostic() {
      const destination = await dialog.showSaveDialog(window, {
        title: "导出脱敏诊断摘要（目标必须不存在，不上传）",
        defaultPath: "easyai-diagnostic.json",
        filters: [{ name: "Easy-AI 诊断摘要", extensions: ["json"] }],
      });
      return destination.canceled ? null : (destination.filePath ?? null);
    },
    async exportProject() {
      const destination = await dialog.showSaveDialog(window, {
        title: "导出已保存工程（目标必须不存在）",
        defaultPath: "project-copy.easyai.json",
        filters: [{ name: "Easy-AI 工程", extensions: ["json"] }],
      });
      return destination.canceled ? null : (destination.filePath ?? null);
    },
    async exportBundle() {
      const destination = await dialog.showOpenDialog(window, {
        title: "选择代码导出父目录（创建新的 easyai-code 子目录，不覆盖）",
        properties: ["openDirectory"],
      });
      return destination.canceled ? null : (destination.filePaths[0] ?? null);
    },
  },
);
window.webContents.on("render-process-gone", () => workflow.dispose());
window.webContents.on("destroyed", () => workflow.dispose());
for (const channel of WORKFLOW_CHANNELS) {
  ipcMain.handle(channel, (event, ...args: unknown[]) => {
    authorizeSender(event);
    return workflow.invoke(channel, args);
  });
}
ipcMain.handle("easyai:runs:subscribe", (event, ...args: unknown[]) => {
  authorizeSender(event);
  if (args.length !== 3) throw new Error("IPC参数无效。");
  workflow.subscribe(args[0], args[1], args[2]);
});
ipcMain.handle("easyai:runs:unsubscribe", (event, ...args: unknown[]) => {
  authorizeSender(event);
  if (args.length !== 1) throw new Error("IPC参数无效。");
  workflow.unsubscribe(args[0]);
});
let quitPending = false;
async function requestQuit(): Promise<void> {
  if (quitPending || quitting) return;
  quitPending = true;
  try {
    if (draftDirty) {
      const answer = await dialog.showMessageBox(window, {
        type: "warning",
        title: "仍有未保存编辑",
        message: "放弃未保存的编辑并退出？",
        detail:
          "选择留在应用，可等待自动保存、手动重试或导出当前草稿。已保存工程不会删除。",
        buttons: ["留在应用", "放弃未保存编辑并退出"],
        defaultId: 0,
        cancelId: 0,
      });
      if (answer.response !== 1) return;
    }
    if (
      backend &&
      backend.process.exitCode === null &&
      backend.process.signalCode === null
    ) {
      const activity = await backend.request<{ activeRunIds: string[] }>(
        "GET",
        "/api/v1/local/activity",
      );
      if (activity.activeRunIds.length) {
        const answer = await dialog.showMessageBox(window, {
          type: "question",
          title: "本地任务仍在运行",
          message: "停止本地训练并退出？",
          detail: "取消会保留已有日志与产物。确认进程停止后应用才会退出。",
          buttons: ["留在应用", "停止任务并退出"],
          defaultId: 0,
          cancelId: 0,
        });
        if (answer.response !== 1) return;
        for (const runId of activity.activeRunIds)
          await backend.request("POST", `/api/v1/runs/${runId}/cancel`);
        const deadline = Date.now() + 30000;
        while (true) {
          const states = await Promise.all(
            activity.activeRunIds.map((runId) =>
              backend!.request<{ status: string }>(
                "GET",
                `/api/v1/runs/${runId}`,
              ),
            ),
          );
          if (
            states.every((state) =>
              ["SUCCEEDED", "FAILED", "CANCELLED", "INTERRUPTED"].includes(
                state.status,
              ),
            )
          )
            break;
          if (Date.now() > deadline)
            throw new Error("尚未确认本地进程已停止，应用将保持打开。");
          await delay(100);
        }
      }
    }
    workflow.dispose();
    await backend?.stop();
    quitting = true;
    app.quit();
  } catch (error) {
    await dialog.showMessageBox(window, {
      type: "error",
      title: "无法安全退出",
      message:
        error instanceof Error
          ? error.message
          : "无法确认任务状态，应用将保持打开。",
    });
  } finally {
    quitPending = false;
  }
}
window.on("close", (event) => {
  if (!quitting) {
    event.preventDefault();
    void requestQuit();
  }
});
app.on("second-instance", () => {
  if (window.isMinimized()) window.restore();
  window.focus();
});

const repository = join(here, "../../..");
const launch = backendLocation(
  app.isPackaged,
  process.resourcesPath,
  repository,
  process.platform,
);
try {
  backend = await startBackend(
    launch.executable,
    launch.cwd,
    10000,
    join(app.getPath("userData"), "local-state"),
    launch.args,
  );
  status = { ready: true, message: "本地服务已就绪。" };
  backend.process.once("exit", () => {
    if (quitting || window.isDestroyed()) return;
    workflow.dispose();
    status = { ready: false, message: "本地服务已退出，请重新启动应用。" };
    // Preserve the live editor draft; reloading here would silently erase unsaved work.
    window.webContents.send("easyai:status:changed", status);
  });
} catch (error) {
  status = {
    ready: false,
    message: error instanceof Error ? error.message : "本地服务无法启动。",
  };
}
await window.loadURL("easyai://app/index.html");
app.on("before-quit", (event) => {
  if (!quitting) {
    event.preventDefault();
    void requestQuit();
  }
});
app.on("window-all-closed", () => {
  if (!quitting) void requestQuit();
});
