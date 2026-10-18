import { contextBridge, ipcRenderer, type IpcRendererEvent } from "electron";
import type { DesktopAPI, SubscriptionMessage } from "./bridge.js";
const api: DesktopAPI = {
  local: {
    preflight: (request) =>
      ipcRenderer.invoke("easyai:local:preflight", request),
  },
  connections: {
    listProfiles: () => ipcRenderer.invoke("easyai:connections:listProfiles"),
    createProfile: (request) =>
      ipcRenderer.invoke("easyai:connections:createProfile", request),
    updateProfile: (targetId, request) =>
      ipcRenderer.invoke("easyai:connections:updateProfile", targetId, request),

    authenticate: (
      projectId,
      requestId,
      identityRequestId,
      username,
      password,
      target,
    ) =>
      ipcRenderer.invoke(
        "easyai:connections:authenticate",
        projectId,
        requestId,
        identityRequestId,
        username,
        password,
        ...(target ? [target] : []),
      ),
    cancelAuth: (projectId, requestId) =>
      ipcRenderer.invoke("easyai:connections:cancelAuth", projectId, requestId),
    close: (projectId, connectionId) =>
      ipcRenderer.invoke("easyai:connections:close", projectId, connectionId),
    current: (projectId, connectionId) =>
      ipcRenderer.invoke("easyai:connections:current", projectId, connectionId),
    probe: (projectId, requestId, endpoint) =>
      ipcRenderer.invoke(
        "easyai:connections:probe",
        projectId,
        requestId,
        endpoint,
      ),
    confirm: (projectId, requestId, fingerprint) =>
      ipcRenderer.invoke(
        "easyai:connections:confirm",
        projectId,
        requestId,
        fingerprint,
      ),
    cancel: (projectId, requestId) =>
      ipcRenderer.invoke("easyai:connections:cancel", projectId, requestId),
  },
  environments: {
    discover: (request) =>
      ipcRenderer.invoke("easyai:environments:discover", request),
    probe: (request) =>
      ipcRenderer.invoke("easyai:environments:probe", request),
    cancel: (request) =>
      ipcRenderer.invoke("easyai:environments:cancel", request),
  },
  status: {
    get: () => ipcRenderer.invoke("easyai:status:get"),
    subscribe: (onStatus) => {
      const listener = (
        _: IpcRendererEvent,
        status: { ready: boolean; message: string },
      ) => onStatus(status);
      ipcRenderer.on("easyai:status:changed", listener);
      return () => {
        ipcRenderer.removeListener("easyai:status:changed", listener);
      };
    },
  },
  selections: {
    pick: (kind) => ipcRenderer.invoke("easyai:selections:pick", kind),
  },
  projects: {
    setDirty: (dirty) => ipcRenderer.invoke("easyai:projects:dirty", dirty),
    current: () => ipcRenderer.invoke("easyai:projects:current"),
    open: (id) => ipcRenderer.invoke("easyai:projects:open", id),
    create: (id, name, template = "mnist-cnn") =>
      ipcRenderer.invoke("easyai:projects:create", id, name, template),
    importProject: () => ipcRenderer.invoke("easyai:projects:import"),
    exportProject: (project) =>
      ipcRenderer.invoke(
        "easyai:projects:export",
        ...(project ? [project] : []),
      ),
    save: (project, revision) =>
      ipcRenderer.invoke("easyai:projects:save", project, revision),
    compile: (project, requestId) =>
      ipcRenderer.invoke("easyai:projects:compile", project, requestId),
  },
  runs: {
    bind: (request) => ipcRenderer.invoke("easyai:runs:bind", request),
    resume: (runId, projectId, connectionId) =>
      ipcRenderer.invoke("easyai:runs:resume", runId, projectId, connectionId),
    list: (id, offset, limit) =>
      ipcRenderer.invoke("easyai:runs:list", id, offset, limit),
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
