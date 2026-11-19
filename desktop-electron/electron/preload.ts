import { contextBridge, ipcRenderer } from "electron";

function invoke<T>(channel: string, payload?: unknown): Promise<T> {
  return ipcRenderer.invoke(channel, payload) as Promise<T>;
}

const bridge = {
  app: {
    info: () => invoke("app:info"),
    openExternal: (url: string) => invoke("app:open-external", { url }),
  },
  window: {
    minimize: () => invoke("window:minimize"),
    toggleMaximize: () => invoke("window:toggle-maximize"),
    close: () => invoke("window:close"),
  },
  auth: {
    login: (email: string, password: string, remember = true) =>
      invoke("auth:login", { email, password, remember }),
    google: (remember = true) => invoke("auth:google", { remember }),
    cancelGoogle: () => invoke("auth:google-cancel"),
    bootstrap: () => invoke("auth:bootstrap"),
    restore: () => invoke("auth:restore"),
    logout: () => invoke("auth:logout"),
    savedAccounts: () => invoke("auth:saved-accounts"),
  },
  api: {
    request: (request: unknown) => invoke("api:request", request),
  },
  files: {
    pick: (request: unknown) => invoke("files:pick", request),
    open: (path: string) => invoke("files:open", { path }),
    reveal: (path: string) => invoke("files:reveal", { path }),
    ensureDir: (path: string) => invoke("files:ensure-dir", { path }),
    readImage: (path: string) => invoke("files:read-image", { path }),
  },
  media: {
    url: (request: unknown) => invoke("media:url", request),
  },
  preferences: {
    getDevice: () => invoke("preferences:device:get"),
    setDevice: (request: unknown) => invoke("preferences:device:set", request),
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
  templates: {
    list: () => invoke("templates:list"),
    install: (request: unknown) => invoke("templates:install", request),
    preview: (request: unknown) => invoke("templates:preview", request),
    onChange: (callback: (payload: unknown) => void) => {
      const listener = (_event: unknown, payload: unknown) => callback(payload);
      ipcRenderer.on("templates:changed", listener);
      return () => ipcRenderer.removeListener("templates:changed", listener);
    },
  },
  videoTemplates: {
    list: () => invoke("video-templates:list"),
    read: (id: string) => invoke("video-templates:read", { id }),
    remove: (id: string) => invoke("video-templates:delete", { id }),
    onChange: (callback: (payload: unknown) => void) => {
      const listener = (_event: unknown, payload: unknown) => callback(payload);
      ipcRenderer.on("video-templates:changed", listener);
      return () => ipcRenderer.removeListener("video-templates:changed", listener);
    },
  },
  diagnostics: {
    send: (note?: string) => invoke("diagnostics:send", { note }),
  },
  updates: {
    check: () => invoke("updates:check"),
    open: (offer: unknown) => invoke("updates:open", offer),
  },
  vizzy: {
    attach: (bounds: unknown) => invoke("vizzy:attach", bounds),
    detach: () => invoke("vizzy:detach"),
    setBounds: (bounds: unknown) => invoke("vizzy:set-bounds", bounds),
    state: () => invoke("vizzy:state"),
    probe: () => invoke("vizzy:probe"),
    reload: () => invoke("vizzy:reload"),
    save: () => invoke("vizzy:save"),
    open: () => invoke("vizzy:open"),
    openPath: (path: string) => invoke("vizzy:open-path", { path }),
    export: (options: unknown) => invoke("vizzy:export", options ?? {}),
    cancelExport: (jobId: string) => invoke("vizzy:export:cancel", { jobId }),
    renders: () => invoke("vizzy:renders:list"),
    deleteRender: (name: string) => invoke("vizzy:renders:delete", { name }),
    revealRender: (name: string) => invoke("vizzy:renders:reveal", { name }),
    renderUrl: (name: string) => invoke("vizzy:renders:url", { name }),
    setVisible: (visible: boolean) => invoke("vizzy:set-visible", { visible }),
    templateOptions: () => invoke("vizzy:template-options"),
    saveTemplate: (input: unknown) => invoke("vizzy:save-template", input),
    previewTemplate: (id: string) => invoke("vizzy:preview-template", { id }),
    openLibrary: () => invoke("vizzy:open-library"),
    renderTemplate: (request: unknown) => invoke("vizzy:render-template", request),
    onState: (callback: (state: unknown) => void) => {
      const listener = (_event: unknown, state: unknown) => callback(state);
      ipcRenderer.on("vizzy:state", listener);
      return () => ipcRenderer.removeListener("vizzy:state", listener);
    },
    onExportProgress: (callback: (payload: unknown) => void) => {
      const listener = (_event: unknown, payload: unknown) => callback(payload);
      ipcRenderer.on("vizzy:export:progress", listener);
      return () => ipcRenderer.removeListener("vizzy:export:progress", listener);
    },
  },
};

contextBridge.exposeInMainWorld("camxora", bridge);
