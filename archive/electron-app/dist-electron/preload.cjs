// electron/preload.ts
var import_electron = require("electron");
var api = {
  bridgeVersion: 1,
  getData: () => import_electron.ipcRenderer.invoke("mg:getData"),
  setData: (data) => import_electron.ipcRenderer.invoke("mg:setData", data),
  appendHistory: (item) => import_electron.ipcRenderer.invoke("mg:appendHistory", item),
  reset: () => import_electron.ipcRenderer.invoke("mg:reset"),
  closeWindow: () => import_electron.ipcRenderer.invoke("mg:close"),
  enqueueJob: (payload) => import_electron.ipcRenderer.invoke("mg:queue:enqueue", payload),
  cancelJob: (jobId) => import_electron.ipcRenderer.invoke("mg:queue:cancel", jobId),
  getQueueState: () => import_electron.ipcRenderer.invoke("mg:queue:state"),
  onJobEvent: (listener) => {
    const handler = (_evt, event) => listener(event);
    import_electron.ipcRenderer.on("mg:jobEvent", handler);
    return () => import_electron.ipcRenderer.off("mg:jobEvent", handler);
  },
  ngrokStatus: () => import_electron.ipcRenderer.invoke("mg:ngrok:status"),
  ngrokStart: (input) => import_electron.ipcRenderer.invoke("mg:ngrok:start", input),
  ngrokStop: () => import_electron.ipcRenderer.invoke("mg:ngrok:stop"),
  openPath: (targetPath) => import_electron.ipcRenderer.invoke("mg:openPath", targetPath),
  showItemInFolder: (targetPath) => import_electron.ipcRenderer.invoke("mg:showItemInFolder", targetPath),
  sunoGetSongOutputDirs: (songUid) => import_electron.ipcRenderer.invoke("mg:suno:getSongOutputDirs", songUid),
  sunoGetBatchRunDirs: (batchId) => import_electron.ipcRenderer.invoke("mg:suno:getBatchRunDirs", batchId),
  pickPath: (opts) => import_electron.ipcRenderer.invoke("mg:pickPath", opts),
  pickDirectories: (opts) => import_electron.ipcRenderer.invoke("mg:pickDirectories", opts),
  videoMergeStart: (input) => import_electron.ipcRenderer.invoke("mg:videoMerge:start", input),
  onVideoMergeEvent: (listener) => {
    const handler = (_evt, event) => listener(event);
    import_electron.ipcRenderer.on("mg:videoMergeEvent", handler);
    return () => import_electron.ipcRenderer.off("mg:videoMergeEvent", handler);
  },
  videoRenderStart: (input) => import_electron.ipcRenderer.invoke("mg:videoRender:start", input),
  videoRenderStartBatch: (input) => import_electron.ipcRenderer.invoke("mg:videoRender:startBatch", input),
  videoRenderStop: () => import_electron.ipcRenderer.invoke("mg:videoRender:stop"),
  videoRenderStartLivePreview: (input) => import_electron.ipcRenderer.invoke("mg:videoRender:startLivePreview", input),
  videoRenderUpdateLivePreview: (input) => import_electron.ipcRenderer.invoke("mg:videoRender:updateLivePreview", input),
  videoRenderStopLivePreview: () => import_electron.ipcRenderer.invoke("mg:videoRender:stopLivePreview"),
  listMp3s: (dirPath) => import_electron.ipcRenderer.invoke("mg:listMp3s", dirPath),
  videoRenderAutoLatestBatch: (input) => import_electron.ipcRenderer.invoke("mg:videoRender:autoLatestBatch", input),
  videoRenderPreviewPng: (input) => import_electron.ipcRenderer.invoke("mg:videoRender:previewPng", input),
  webglExportGetJob: (input) => import_electron.ipcRenderer.invoke("mg:webglExport:getJob", input),
  webglExportReady: (input) => {
    import_electron.ipcRenderer.send("mg:webglExport:ready", input);
  },
  onVideoRenderEvent: (listener) => {
    const handler = (_evt, event) => listener(event);
    import_electron.ipcRenderer.on("mg:videoRenderEvent", handler);
    return () => import_electron.ipcRenderer.off("mg:videoRenderEvent", handler);
  },
  videoTemplatesList: () => import_electron.ipcRenderer.invoke("mg:videoTemplates:list"),
  videoTemplatesRead: (input) => import_electron.ipcRenderer.invoke("mg:videoTemplates:read", input),
  videoTemplatesSave: (input) => import_electron.ipcRenderer.invoke("mg:videoTemplates:save", input),
  videoTemplatesDelete: (input) => import_electron.ipcRenderer.invoke("mg:videoTemplates:delete", input),
  imageSamplesList: (input) => import_electron.ipcRenderer.invoke("mg:imageSamples:list", input),
  generateBackgroundImage: (input) => import_electron.ipcRenderer.invoke("mg:image:generateBackground", input),
  generateBackgroundPromptImage: (input) => import_electron.ipcRenderer.invoke("mg:image:generateBackgroundPrompt", input),
  generateThumbnailImage: (input) => import_electron.ipcRenderer.invoke("mg:image:generateThumbnail", input),
  generateThumbnailBestOf: (input) => import_electron.ipcRenderer.invoke("mg:image:generateThumbnailBestOf", input),
  listGeneratedImages: (input) => import_electron.ipcRenderer.invoke("mg:image:listGenerated", input),
  contentBootstrap: () => import_electron.ipcRenderer.invoke("mg:content:bootstrap"),
  contentUpsert: (input) => import_electron.ipcRenderer.invoke("mg:content:upsert", input),
  contentDelete: (input) => import_electron.ipcRenderer.invoke("mg:content:delete", input),
  contentBulkUpsertTextStyles: (input) => import_electron.ipcRenderer.invoke("mg:content:bulkUpsertTextStyles", input),
  contentBulkUpsertCarModels: (input) => import_electron.ipcRenderer.invoke("mg:content:bulkUpsertCarModels", input),
  testDbConnection: (cfg) => import_electron.ipcRenderer.invoke("mg:db:testConnection", cfg),
  ensureDbAndMigrate: (cfg) => import_electron.ipcRenderer.invoke("mg:db:ensureAndMigrate", cfg),
  pathExists: (targetPath) => import_electron.ipcRenderer.invoke("mg:pathExists", targetPath),
  downloadFfmpeg: (opts) => import_electron.ipcRenderer.invoke("mg:ffmpeg:download", opts),
  polishLyrics: (input) => import_electron.ipcRenderer.invoke("mg:lyrics:polish", input),
  poolsStats: (cfg) => import_electron.ipcRenderer.invoke("mg:pools:stats", cfg),
  poolsImport: (input) => import_electron.ipcRenderer.invoke("mg:pools:import", input),
  poolsList: (input) => import_electron.ipcRenderer.invoke("mg:pools:list", input),
  poolsGenerate: (input) => import_electron.ipcRenderer.invoke("mg:pools:generate", input),
  clearGenerated: (cfg) => import_electron.ipcRenderer.invoke("mg:db:clearGenerated", cfg),
  poolsClear: (input) => import_electron.ipcRenderer.invoke("mg:pools:clear", input)
};
try {
  import_electron.contextBridge.exposeInMainWorld("mgApi", api);
} catch (e) {
  console.error("Failed to expose mgApi", e);
}
try {
  import_electron.ipcRenderer.send("mg:preload:ready", { bridgeVersion: api.bridgeVersion });
} catch (e) {
  console.error("Failed to signal preload ready", e);
}
//# sourceMappingURL=preload.cjs.map
