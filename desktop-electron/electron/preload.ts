import { contextBridge, ipcRenderer } from "electron";

function invoke<T>(channel: string, payload?: unknown): Promise<T> {
  return ipcRenderer.invoke(channel, payload) as Promise<T>;
}

const bridge = {
  app: {
    info: () => invoke("app:info"),
  },
  window: {
    minimize: () => invoke("window:minimize"),
    toggleMaximize: () => invoke("window:toggle-maximize"),
    close: () => invoke("window:close"),
  },
  auth: {
    login: (email: string, password: string, remember = true) =>
      invoke("auth:login", { email, password, remember }),
    restore: () => invoke("auth:restore"),
    logout: () => invoke("auth:logout"),
    savedAccounts: () => invoke("auth:saved-accounts"),
  },
  api: {
    request: (request: unknown) => invoke("api:request", request),
  },
  files: {
    pick: (request: unknown) => invoke("files:pick", request),
  },
  media: {
    url: (request: unknown) => invoke("media:url", request),
  },
  ffmpeg: {
    available: () => invoke("ffmpeg:available"),
    probe: (request: unknown) => invoke("ffmpeg:probe", request),
    run: (request: unknown) => invoke("ffmpeg:run", request),
    cancel: (jobId: string) => invoke("ffmpeg:cancel", { jobId }),
    onProgress: (callback: (payload: unknown) => void) => {
      const listener = (_event: unknown, payload: unknown) => callback(payload);
      ipcRenderer.on("ffmpeg:progress", listener);
      return () => ipcRenderer.removeListener("ffmpeg:progress", listener);
    },
    onDone: (callback: (payload: unknown) => void) => {
      const listener = (_event: unknown, payload: unknown) => callback(payload);
      ipcRenderer.on("ffmpeg:done", listener);
      return () => ipcRenderer.removeListener("ffmpeg:done", listener);
    },
    onFailed: (callback: (payload: unknown) => void) => {
      const listener = (_event: unknown, payload: unknown) => callback(payload);
      ipcRenderer.on("ffmpeg:failed", listener);
      return () => ipcRenderer.removeListener("ffmpeg:failed", listener);
    },
  },
  diagnostics: {
    send: (note?: string) => invoke("diagnostics:send", { note }),
  },
};

contextBridge.exposeInMainWorld("camxora", bridge);
