/// <reference types="vite/client" />

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

declare global {
  interface Window {
    mgApi?: {
      bridgeVersion: number;
      getData: () => Promise<AppData>;
      setData: (data: AppData) => Promise<{ ok: boolean }>;
      appendHistory: (item: HistoryItem) => Promise<{ ok: boolean }>;
      reset: () => Promise<AppData>;
      closeWindow: () => Promise<{ ok: boolean }>;
      enqueueJob: (payload: JobPayload) => Promise<{ jobId: string }>;
      cancelJob: (jobId: string) => Promise<{ ok: boolean }>;
      getQueueState: () => Promise<{ running: boolean; currentJobId: string | null; queuedCount: number }>;
      onJobEvent: (listener: (event: JobEvent) => void) => () => void;
      openPath: (targetPath: string) => Promise<string>;
      showItemInFolder: (targetPath: string) => Promise<{ ok: boolean }>;
      sunoGetSongOutputDirs: (songUid: string) => Promise<{ ok: true; okDir: string | null; altDir: string | null } | { ok: false; message: string }>;
      sunoGetBatchRunDirs: (batchId: string) => Promise<{ ok: true; okDir: string | null; altDir: string | null } | { ok: false; message: string }>;
      pickPath: (opts: {
        kind: "file" | "directory";
        defaultPath?: string;
        title?: string;
        filters?: { name: string; extensions: string[] }[];
      }) => Promise<{ canceled: true } | { canceled: false; path: string }>;
      pickDirectories: (opts?: { title?: string; defaultPath?: string }) => Promise<{ canceled: true } | { canceled: false; paths: string[] }>;
      videoMergeStart: (input: { directories: string[]; exportSettings: VideoExportSettings }) => Promise<{ ok: true; runId: string } | { ok: false; message: string }>;
      onVideoMergeEvent: (listener: (event: VideoMergeEvent) => void) => () => void;
      videoRenderStart: (input: VideoRenderStartInput) => Promise<{ ok: true; runId: string } | { ok: false; message: string }>;
      videoRenderStartBatch: (input: { mp3DirPath: string; backgroundPath: string; template: unknown; logoPath?: string; outputDir: string; }) => Promise<{ ok: true; runId: string } | { ok: false; message: string }>;
      videoRenderStop: () => Promise<{ ok: boolean }>;
      listMp3s: (dirPath: string) => Promise<{ ok: boolean; files: { path: string; name: string }[] }>;
      videoRenderAutoLatestBatch: (input?: { templatePath?: string }) => Promise<{ ok: true; runId: string } | { ok: false; message: string }>;
      videoRenderPreviewPng: (input: {
        mp3Path?: string;
        backgroundPath: string;
        templatePath?: string;
        template?: unknown;
        logoPath?: string;
        width?: number;
        height?: number;
        frame?: number;
      }) => Promise<{ ok: true; filePath: string; fileUrl: string } | { ok: false; message: string }>;
      onVideoRenderEvent: (listener: (event: VideoRenderEvent) => void) => () => void;
      videoTemplatesList: () => Promise<{ ok: true; items: VideoTemplateListItem[] } | { ok: false; message: string }>;
      videoTemplatesRead: (input: { path: string }) => Promise<{ ok: true; template: unknown } | { ok: false; message: string }>;
      videoTemplatesSave: (input: { label: string; template: unknown }) => Promise<{ ok: true; path: string } | { ok: false; message: string }>;
      videoTemplatesDelete: (input: { path: string }) => Promise<{ ok: true } | { ok: false; message: string }>;
      imageSamplesList: (input: { folderPath: string }) =>
        Promise<{ ok: true; items: ImageSampleFile[] } | { ok: false; message: string }>;
      generateBackgroundImage: (input: {
        prompt: string;
        sampleFilePath: string;
        resolution: "1920x1080" | "1080x1920";
        outputDir: string;
        outputFileName?: string;
        apiKey?: string;
      }) => Promise<{ ok: true; filePath: string; fileUrl: string; meta?: ImageGenMeta } | { ok: false; message: string }>;
      generateBackgroundPromptImage: (input: {
        prompt: string;
        resolution: "1920x1080" | "1080x1920";
        outputDir: string;
        outputFileName?: string;
        apiKey?: string;
      }) => Promise<{ ok: true; filePath: string; fileUrl: string; meta?: ImageGenMeta } | { ok: false; message: string }>;
      generateThumbnailImage: (input: {
        prompt: string;
        backgroundFilePath: string;
        resolution: "1920x1080" | "1080x1920";
        outputDir: string;
        outputFileName?: string;
        apiKey?: string;
      }) => Promise<{ ok: true; filePath: string; fileUrl: string; meta?: ImageGenMeta } | { ok: false; message: string }>;
      generateThumbnailBestOf: (input: {
        prompt: string;
        backgroundFilePath: string;
        resolution: "1920x1080" | "1080x1920";
        outputDir: string;
        finalFileName?: string;
        keepCandidates?: boolean;
        apiKey?: string;
        count?: number;
      }) => Promise<
        | { ok: true; filePath: string; fileUrl: string; candidates: Array<{ filePath: string; fileUrl: string; score: number }> }
        | { ok: false; message: string }
      >;
      listGeneratedImages: (input: { outputDir: string; kind: "background" | "thumbnail"; limit?: number }) => Promise<
        | { ok: true; items: Array<{ filePath: string; fileUrl: string; mtimeMs: number }> }
        | { ok: false; message: string }
      >;

      contentBootstrap: () => Promise<ContentBootstrapResult>;
      contentUpsert: (input: ContentUpsertRequest) => Promise<ContentUpsertResult>;
      contentDelete: (input: ContentDeleteRequest) => Promise<ContentDeleteResult>;
      contentBulkUpsertTextStyles: (input: ContentBulkUpsertTextStylesRequest) => Promise<ContentBulkUpsertTextStylesResult>;
      contentBulkUpsertCarModels: (input: ContentBulkUpsertCarModelsRequest) => Promise<ContentBulkUpsertCarModelsResult>;
      testDbConnection: (cfg: { host: string; port: number; user: string; password: string; database: string }) => Promise<{ ok: boolean; message: string }>;
      ensureDbAndMigrate: (cfg: { host: string; port: number; user: string; password: string; database: string }) => Promise<{ ok: boolean; message: string }>;
      pathExists: (targetPath: string) => Promise<{ exists: boolean }>;
      downloadFfmpeg: (opts: { installDir: string }) => Promise<{ ok: true; ffmpegPath: string; installDir: string }>;
      polishLyrics: (input: { lyrics: string; strength: number; apiKey?: string }) =>
        Promise<{ ok: true; lyrics: string } | { ok: false; message: string }>;
      poolsStats: (cfg: { host: string; port: number; user: string; password: string; database: string }) => Promise<{
        openings: { total: number; unused: number };
        titles: { total: number; unused: number };
        albums: { total: number; unused: number };
      }>;
      poolsImport: (input: {
        kind: "titles" | "albums" | "openings";
        filePath: string;
        cfg: { host: string; port: number; user: string; password: string; database: string };
      }) => Promise<{ inserted: number }>;
      poolsList: (input: {
        kind: "titles" | "albums" | "openings";
        limit: number;
        offset: number;
        cfg: { host: string; port: number; user: string; password: string; database: string };
      }) => Promise<
        | { kind: "titles"; rows: Array<{ id: number; text: string; usedCount: number; createdAt: string }> }
        | { kind: "albums"; rows: Array<{ id: number; text: string; usedCount: number; createdAt: string }> }
        | { kind: "openings"; rows: Array<{ id: number; line1: string; line2: string; usedCount: number; createdAt: string }> }
      >;
      poolsGenerate: (input: {
        kind: "titles" | "albums" | "openings";
        count: number;
        cfg: { host: string; port: number; user: string; password: string; database: string };
      }) => Promise<{ inserted: number }>;
      clearGenerated: (cfg: { host: string; port: number; user: string; password: string; database: string }) =>
        Promise<{ ok: true } | { ok: false; message: string }>;
      poolsClear: (input: {
        kind: "titles" | "albums" | "openings";
        cfg: { host: string; port: number; user: string; password: string; database: string };
      }) => Promise<{ ok: true } | { ok: false; message: string }>;

      ngrokStatus: () => Promise<{
        running: boolean;
        publicUrl: string | null;
        callbackUrl: string | null;
        localPort: number | null;
        lastError: string | null;
        callbackPort: number | null;
      }>;
      ngrokStart: (input?: { ngrokPath?: string }) => Promise<
        | {
            ok: true;
            status: {
              running: boolean;
              publicUrl: string | null;
              callbackUrl: string | null;
              localPort: number | null;
              lastError: string | null;
            };
          }
        | { ok: false; message: string }
      >;
      ngrokStop: () => Promise<{
        ok: true;
        status: {
          running: boolean;
          publicUrl: string | null;
          callbackUrl: string | null;
          localPort: number | null;
          lastError: string | null;
        };
      }>;
      videoRenderStartLivePreview: (input: { mp3Path?: string; backgroundPath: string; template: unknown; logoPath?: string; }) => Promise<{ ok: boolean; message?: string }>;
      videoRenderUpdateLivePreview: (input: { time?: number; template?: unknown; backgroundPath?: string; logoPath?: string; audioPath?: string; }) => Promise<{ ok: boolean }>;
      videoRenderStopLivePreview: () => Promise<{ ok: boolean }>;
    };
  }
}
