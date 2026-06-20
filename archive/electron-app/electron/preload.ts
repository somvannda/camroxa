import { contextBridge, ipcRenderer } from "electron";
import type {
  AppData,
  ContentBootstrapResult,
  ContentBulkUpsertCarModelsRequest,
  ContentBulkUpsertCarModelsResult,
  ContentBulkUpsertTextStylesRequest,
  ContentBulkUpsertTextStylesResult,
  ContentDeleteRequest,
  ContentDeleteResult,
  ContentUpsertRequest,
  ContentUpsertResult,
  HistoryItem,
  ImageGenMeta,
  ImageSampleFile,
  JobEvent,
  JobPayload,
  VideoExportSettings,
  VideoMergeEvent,
  VideoRenderEvent,
  VideoRenderStartInput,
  VideoTemplateListItem,
} from "../shared/app-types";

const api = {
  bridgeVersion: 1,
  getData: () => ipcRenderer.invoke("mg:getData") as Promise<AppData>,
  setData: (data: AppData) => ipcRenderer.invoke("mg:setData", data) as Promise<{ ok: boolean }>,
  appendHistory: (item: HistoryItem) => ipcRenderer.invoke("mg:appendHistory", item) as Promise<{ ok: boolean }>,
  reset: () => ipcRenderer.invoke("mg:reset") as Promise<AppData>,
  closeWindow: () => ipcRenderer.invoke("mg:close") as Promise<{ ok: boolean }>,
  enqueueJob: (payload: JobPayload) => ipcRenderer.invoke("mg:queue:enqueue", payload) as Promise<{ jobId: string }>,
  cancelJob: (jobId: string) => ipcRenderer.invoke("mg:queue:cancel", jobId) as Promise<{ ok: boolean }>,
  getQueueState: () => ipcRenderer.invoke("mg:queue:state") as Promise<{ running: boolean; currentJobId: string | null; queuedCount: number }>,
  onJobEvent: (listener: (event: JobEvent) => void) => {
    const handler = (_evt: Electron.IpcRendererEvent, event: JobEvent) => listener(event);
    ipcRenderer.on("mg:jobEvent", handler);
    return () => ipcRenderer.off("mg:jobEvent", handler);
  },
  ngrokStatus: () => ipcRenderer.invoke("mg:ngrok:status") as Promise<{
    running: boolean;
    publicUrl: string | null;
    callbackUrl: string | null;
    localPort: number | null;
    lastError: string | null;
    callbackPort: number | null;
  }>,
  ngrokStart: (input?: { ngrokPath?: string }) =>
    ipcRenderer.invoke("mg:ngrok:start", input) as Promise<
      | { ok: true; status: { running: boolean; publicUrl: string | null; callbackUrl: string | null; localPort: number | null; lastError: string | null } }
      | { ok: false; message: string }
    >,
  ngrokStop: () =>
    ipcRenderer.invoke("mg:ngrok:stop") as Promise<{ ok: true; status: { running: boolean; publicUrl: string | null; callbackUrl: string | null; localPort: number | null; lastError: string | null } }>,
  openPath: (targetPath: string) => ipcRenderer.invoke("mg:openPath", targetPath) as Promise<string>,
  showItemInFolder: (targetPath: string) => ipcRenderer.invoke("mg:showItemInFolder", targetPath) as Promise<{ ok: boolean }>,
  sunoGetSongOutputDirs: (songUid: string) =>
    ipcRenderer.invoke("mg:suno:getSongOutputDirs", songUid) as Promise<
      | { ok: true; okDir: string | null; altDir: string | null }
      | { ok: false; message: string }
    >,
  sunoGetBatchRunDirs: (batchId: string) =>
    ipcRenderer.invoke("mg:suno:getBatchRunDirs", batchId) as Promise<
      | { ok: true; okDir: string | null; altDir: string | null }
      | { ok: false; message: string }
    >,
  pickPath: (opts: {
    kind: "file" | "directory";
    defaultPath?: string;
    title?: string;
    filters?: { name: string; extensions: string[] }[];
  }) =>
    ipcRenderer.invoke("mg:pickPath", opts) as Promise<{ canceled: true } | { canceled: false; path: string }>,
  pickDirectories: (opts?: { title?: string; defaultPath?: string }) =>
    ipcRenderer.invoke("mg:pickDirectories", opts) as Promise<{ canceled: true } | { canceled: false; paths: string[] }>,
  videoMergeStart: (input: { directories: string[]; exportSettings: VideoExportSettings }) =>
    ipcRenderer.invoke("mg:videoMerge:start", input) as Promise<{ ok: true; runId: string } | { ok: false; message: string }>,
  onVideoMergeEvent: (listener: (event: VideoMergeEvent) => void) => {
    const handler = (_evt: Electron.IpcRendererEvent, event: VideoMergeEvent) => listener(event);
    ipcRenderer.on("mg:videoMergeEvent", handler);
    return () => ipcRenderer.off("mg:videoMergeEvent", handler);
  },
  videoRenderStart: (input: VideoRenderStartInput) =>
    ipcRenderer.invoke("mg:videoRender:start", input) as Promise<{ ok: true; runId: string } | { ok: false; message: string }>,
  videoRenderStartBatch: (input: {
    mp3DirPath: string;
    backgroundPath: string;
    template: unknown;
    logoPath?: string;
    outputDir: string;
    engine?: "python" | "webgl";
  }) => ipcRenderer.invoke("mg:videoRender:startBatch", input) as Promise<{ ok: true; runId: string } | { ok: false; message: string }>,
  videoRenderStop: () => ipcRenderer.invoke("mg:videoRender:stop"),
  videoRenderStartLivePreview: (input: {
    mp3Path?: string;
    backgroundPath: string;
    template: unknown;
    logoPath?: string;
  }) => ipcRenderer.invoke("mg:videoRender:startLivePreview", input) as Promise<{ ok: boolean; message?: string }>,
  videoRenderUpdateLivePreview: (input: {
    time?: number;
    template?: unknown;
    backgroundPath?: string;
    logoPath?: string;
    audioPath?: string;
  }) => ipcRenderer.invoke("mg:videoRender:updateLivePreview", input) as Promise<{ ok: boolean }>,
  videoRenderStopLivePreview: () => ipcRenderer.invoke("mg:videoRender:stopLivePreview") as Promise<{ ok: boolean }>,
  listMp3s: (dirPath: string) => ipcRenderer.invoke("mg:listMp3s", dirPath),
  videoRenderAutoLatestBatch: (input?: { templatePath?: string }) =>
    ipcRenderer.invoke("mg:videoRender:autoLatestBatch", input) as Promise<{ ok: true; runId: string } | { ok: false; message: string }>,
  videoRenderPreviewPng: (input: {
    mp3Path?: string;
    backgroundPath: string;
    templatePath?: string;
    template?: unknown;
    logoPath?: string;
    width?: number;
    height?: number;
    frame?: number;
  }) =>
    ipcRenderer.invoke("mg:videoRender:previewPng", input) as Promise<{ ok: true; filePath: string; fileUrl: string } | { ok: false; message: string }>,
  webglExportGetJob: (input: { jobId: string }) =>
    ipcRenderer.invoke("mg:webglExport:getJob", input) as Promise<{ ok: true; job: any } | { ok: false; message: string }>,
  webglExportReady: (input: { jobId: string; duration: number }) => {
    ipcRenderer.send("mg:webglExport:ready", input);
  },
  onVideoRenderEvent: (listener: (event: VideoRenderEvent) => void) => {
    const handler = (_evt: Electron.IpcRendererEvent, event: VideoRenderEvent) => listener(event);
    ipcRenderer.on("mg:videoRenderEvent", handler);
    return () => ipcRenderer.off("mg:videoRenderEvent", handler);
  },
  videoTemplatesList: () =>
    ipcRenderer.invoke("mg:videoTemplates:list") as Promise<{ ok: true; items: VideoTemplateListItem[] } | { ok: false; message: string }>,
  videoTemplatesRead: (input: { path: string }) =>
    ipcRenderer.invoke("mg:videoTemplates:read", input) as Promise<{ ok: true; template: unknown } | { ok: false; message: string }>,
  videoTemplatesSave: (input: { label: string; template: unknown }) =>
    ipcRenderer.invoke("mg:videoTemplates:save", input) as Promise<{ ok: true; path: string } | { ok: false; message: string }>,
  videoTemplatesDelete: (input: { path: string }) =>
    ipcRenderer.invoke("mg:videoTemplates:delete", input) as Promise<{ ok: true } | { ok: false; message: string }>,
  imageSamplesList: (input: { folderPath: string }) =>
    ipcRenderer.invoke("mg:imageSamples:list", input) as Promise<{ ok: true; items: ImageSampleFile[] } | { ok: false; message: string }>,
  generateBackgroundImage: (input: {
    prompt: string;
    sampleFilePath: string;
    resolution: "1920x1080" | "1080x1920";
    outputDir: string;
    outputFileName?: string;
    apiKey?: string;
  }) =>
    ipcRenderer.invoke("mg:image:generateBackground", input) as Promise<
      | { ok: true; filePath: string; fileUrl: string; meta?: ImageGenMeta }
      | { ok: false; message: string }
    >,
  generateBackgroundPromptImage: (input: {
    prompt: string;
    resolution: "1920x1080" | "1080x1920";
    outputDir: string;
    outputFileName?: string;
    apiKey?: string;
  }) =>
    ipcRenderer.invoke("mg:image:generateBackgroundPrompt", input) as Promise<
      | { ok: true; filePath: string; fileUrl: string; meta?: ImageGenMeta }
      | { ok: false; message: string }
    >,
  generateThumbnailImage: (input: {
    prompt: string;
    backgroundFilePath: string;
    resolution: "1920x1080" | "1080x1920";
    outputDir: string;
    outputFileName?: string;
    apiKey?: string;
  }) =>
    ipcRenderer.invoke("mg:image:generateThumbnail", input) as Promise<
      | { ok: true; filePath: string; fileUrl: string; meta?: ImageGenMeta }
      | { ok: false; message: string }
    >,
  generateThumbnailBestOf: (input: {
    prompt: string;
    backgroundFilePath: string;
    resolution: "1920x1080" | "1080x1920";
    outputDir: string;
    finalFileName?: string;
    keepCandidates?: boolean;
    apiKey?: string;
    count?: number;
  }) =>
    ipcRenderer.invoke("mg:image:generateThumbnailBestOf", input) as Promise<
      | { ok: true; filePath: string; fileUrl: string; candidates: Array<{ filePath: string; fileUrl: string; score: number }> }
      | { ok: false; message: string }
    >,
  listGeneratedImages: (input: { outputDir: string; kind: "background" | "thumbnail"; limit?: number }) =>
    ipcRenderer.invoke("mg:image:listGenerated", input) as Promise<
      | { ok: true; items: Array<{ filePath: string; fileUrl: string; mtimeMs: number }> }
      | { ok: false; message: string }
    >,
  contentBootstrap: () => ipcRenderer.invoke("mg:content:bootstrap") as Promise<ContentBootstrapResult>,
  contentUpsert: (input: ContentUpsertRequest) => ipcRenderer.invoke("mg:content:upsert", input) as Promise<ContentUpsertResult>,
  contentDelete: (input: ContentDeleteRequest) => ipcRenderer.invoke("mg:content:delete", input) as Promise<ContentDeleteResult>,
  contentBulkUpsertTextStyles: (input: ContentBulkUpsertTextStylesRequest) =>
    ipcRenderer.invoke("mg:content:bulkUpsertTextStyles", input) as Promise<ContentBulkUpsertTextStylesResult>,
  contentBulkUpsertCarModels: (input: ContentBulkUpsertCarModelsRequest) =>
    ipcRenderer.invoke("mg:content:bulkUpsertCarModels", input) as Promise<ContentBulkUpsertCarModelsResult>,
  testDbConnection: (cfg: { host: string; port: number; user: string; password: string; database: string }) =>
    ipcRenderer.invoke("mg:db:testConnection", cfg) as Promise<{ ok: boolean; message: string }>,
  ensureDbAndMigrate: (cfg: { host: string; port: number; user: string; password: string; database: string }) =>
    ipcRenderer.invoke("mg:db:ensureAndMigrate", cfg) as Promise<{ ok: boolean; message: string }>,
  pathExists: (targetPath: string) => ipcRenderer.invoke("mg:pathExists", targetPath) as Promise<{ exists: boolean }>,
  downloadFfmpeg: (opts: { installDir: string }) =>
    ipcRenderer.invoke("mg:ffmpeg:download", opts) as Promise<{ ok: true; ffmpegPath: string; installDir: string }>,
  polishLyrics: (input: { lyrics: string; strength: number; apiKey?: string }) =>
    ipcRenderer.invoke("mg:lyrics:polish", input) as Promise<{ ok: true; lyrics: string } | { ok: false; message: string }>,
  poolsStats: (cfg: { host: string; port: number; user: string; password: string; database: string }) =>
    ipcRenderer.invoke("mg:pools:stats", cfg) as Promise<{
      openings: { total: number; unused: number };
      titles: { total: number; unused: number };
      albums: { total: number; unused: number };
    }>,
  poolsImport: (input: {
    kind: "titles" | "albums" | "openings";
    filePath: string;
    cfg: { host: string; port: number; user: string; password: string; database: string };
  }) => ipcRenderer.invoke("mg:pools:import", input) as Promise<{ inserted: number }>,
  poolsList: (input: {
    kind: "titles" | "albums" | "openings";
    limit: number;
    offset: number;
    cfg: { host: string; port: number; user: string; password: string; database: string };
  }) =>
    ipcRenderer.invoke("mg:pools:list", input) as Promise<
      | { kind: "titles"; rows: Array<{ id: number; text: string; usedCount: number; createdAt: string }> }
      | { kind: "albums"; rows: Array<{ id: number; text: string; usedCount: number; createdAt: string }> }
      | { kind: "openings"; rows: Array<{ id: number; line1: string; line2: string; usedCount: number; createdAt: string }> }
    >,
  poolsGenerate: (input: {
    kind: "titles" | "albums" | "openings";
    count: number;
    cfg: { host: string; port: number; user: string; password: string; database: string };
  }) => ipcRenderer.invoke("mg:pools:generate", input) as Promise<{ inserted: number }>,
  clearGenerated: (cfg: { host: string; port: number; user: string; password: string; database: string }) =>
    ipcRenderer.invoke("mg:db:clearGenerated", cfg) as Promise<{ ok: true } | { ok: false; message: string }>,
  poolsClear: (input: {
    kind: "titles" | "albums" | "openings";
    cfg: { host: string; port: number; user: string; password: string; database: string };
  }) => ipcRenderer.invoke("mg:pools:clear", input) as Promise<{ ok: true } | { ok: false; message: string }>,
};

try {
  contextBridge.exposeInMainWorld("mgApi", api);
} catch (e) {
  console.error("Failed to expose mgApi", e);
}

try {
  ipcRenderer.send("mg:preload:ready", { bridgeVersion: api.bridgeVersion });
} catch (e) {
  console.error("Failed to signal preload ready", e);
}

