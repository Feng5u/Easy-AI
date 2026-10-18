import { contextBridge, ipcRenderer } from "electron";
contextBridge.exposeInMainWorld(
  "easyai",
  Object.freeze({
    status: Object.freeze({
      get: () =>
        ipcRenderer.invoke("easyai:status:get") as Promise<{
          ready: boolean;
          message: string;
        }>,
    }),
  }),
);
