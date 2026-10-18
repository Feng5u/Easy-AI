import { contextBridge, ipcRenderer, type IpcRendererEvent } from "electron";
import type { DesktopAPI, SubscriptionMessage } from "./bridge.js";
const api: DesktopAPI = {
  status: { get: () => ipcRenderer.invoke("easyai:status:get") },
  selections: {
    pick: (kind) => ipcRenderer.invoke("easyai:selections:pick", kind),
  },
  projects: {
    current: () => ipcRenderer.invoke("easyai:projects:current"),
    open: (id) => ipcRenderer.invoke("easyai:projects:open", id),
    create: (id, name) =>
      ipcRenderer.invoke("easyai:projects:create", id, name),
    save: (project, revision) =>
      ipcRenderer.invoke("easyai:projects:save", project, revision),
    compile: (project, requestId) =>
      ipcRenderer.invoke("easyai:projects:compile", project, requestId),
  },
  runs: {
    start: (request) => ipcRenderer.invoke("easyai:runs:start", request),
    get: (id) => ipcRenderer.invoke("easyai:runs:get", id),
    cancel: (id) => ipcRenderer.invoke("easyai:runs:cancel", id),
    source: (id) => ipcRenderer.invoke("easyai:runs:source", id),
    logs: (id, stdout, stderr) =>
      ipcRenderer.invoke("easyai:runs:logs", id, stdout, stderr),
    artifacts: (id) => ipcRenderer.invoke("easyai:runs:artifacts", id),
    image: (id, artifact) =>
      ipcRenderer.invoke("easyai:runs:image", id, artifact),
    subscribe: (runId, after, onEvent, onConnection) => {
      const subscriptionId = globalThis.crypto.randomUUID();
      let active = true;
      const listener = (_: IpcRendererEvent, message: SubscriptionMessage) => {
        if (!active || message.subscriptionId !== subscriptionId) return;
        if (message.kind === "event") onEvent(message.event);
        else onConnection(message.state, message.message);
      };
      ipcRenderer.on("easyai:runs:message", listener);
      void ipcRenderer
        .invoke("easyai:runs:subscribe", subscriptionId, runId, after)
        .catch(() => {
          if (active) onConnection("error", "无法订阅运行事件。");
        });
      return () => {
        if (!active) return;
        active = false;
        ipcRenderer.removeListener("easyai:runs:message", listener);
        void ipcRenderer
          .invoke("easyai:runs:unsubscribe", subscriptionId)
          .catch(() => undefined);
      };
    },
  },
};
for (const value of Object.values(api)) Object.freeze(value);
contextBridge.exposeInMainWorld("easyai", Object.freeze(api));
