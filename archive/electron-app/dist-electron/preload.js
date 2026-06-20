// electron/preload.ts
import { contextBridge, ipcRenderer } from "electron";
var api = {
  bridgeVersion: 1,
  getData: () => ipcRenderer.invoke("mg:getData"),
  setData: (data) => ipcRenderer.invoke("mg:setData", data),
  appendHistory: (item) => ipcRenderer.invoke("mg:appendHistory", item),
  reset: () => ipcRenderer.invoke("mg:reset"),
  closeWindow: () => ipcRenderer.invoke("mg:close"),
  enqueueJob: (payload) => ipcRenderer.invoke("mg:queue:enqueue", payload),
  cancelJob: (jobId) => ipcRenderer.invoke("mg:queue:cancel", jobId),
  getQueueState: () => ipcRenderer.invoke("mg:queue:state"),
  onJobEvent: (listener) => {
    const handler = (_evt, event) => listener(event);
    ipcRenderer.on("mg:jobEvent", handler);
    return () => ipcRenderer.off("mg:jobEvent", handler);
  },
  openPath: (targetPath) => ipcRenderer.invoke("mg:openPath", targetPath),
  showItemInFolder: (targetPath) => ipcRenderer.invoke("mg:showItemInFolder", targetPath),
  pickPath: (opts) => ipcRenderer.invoke("mg:pickPath", opts),
  testDbConnection: (cfg) => ipcRenderer.invoke("mg:db:testConnection", cfg),
  ensureDbAndMigrate: (cfg) => ipcRenderer.invoke("mg:db:ensureAndMigrate", cfg),
  pathExists: (targetPath) => ipcRenderer.invoke("mg:pathExists", targetPath),
  downloadFfmpeg: (opts) => ipcRenderer.invoke("mg:ffmpeg:download", opts)
};
contextBridge.exposeInMainWorld("mgApi", api);
//# sourceMappingURL=preload.js.map
