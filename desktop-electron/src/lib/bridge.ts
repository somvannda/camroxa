import type {
  ApiRequest,
  ApiResponse,
  AppInfo,
  BootstrapResult,
  DevicePreferences,
  DownloadChangedEvent,
  DownloadSnapshot,
  InstallTemplateRequest,
  InstallTemplateResult,
  InstalledTemplate,
  IpcResult,
  PickFileRequest,
  PipelineChangedEvent,
  PipelineEnqueueRequest,
  PipelineEnqueueResult,
  PipelineSnapshot,
  SavedAccount,
  TemplateChangedEvent,
  UpdateCheckResult,
  UpdateOffer,
  VideoTemplateChangedEvent,
  VideoTemplateInfo,
  VizzyBounds,
  VizzyExportOutcome,
  VizzyExportProgress,
  VizzyExportSettingsInput,
  VizzyOpenResult,
  VizzyProbe,
  VizzyRenderSummary,
  VizzyRenderTemplateRequest,
  VizzySaveResult,
  VizzySaveTemplateInput,
  VizzyState,
  VizzyTemplateDraftInfo,
  YoutubeAvailability,
  YoutubeUploadChangedEvent,
  YoutubeUploadPlan,
  YoutubeUploadRowQuery,
  YoutubeUploadSnapshot,
  YoutubeUploadStartRequest,
  YoutubeUploadState,
} from "../../electron/shared/types";

export interface CamxoraBridge {
  app: {
    info(): Promise<AppInfo>;
    openExternal(url: string): Promise<IpcResult<boolean>>;
  };
  window: {
    minimize(): Promise<void>;
    toggleMaximize(): Promise<void>;
    close(): Promise<void>;
  };
  auth: {
    login(email: string, password: string, remember?: boolean): Promise<IpcResult<BootstrapResult>>;
    google(remember?: boolean): Promise<IpcResult<BootstrapResult>>;
    googleAvailable(): Promise<IpcResult<{ available: boolean; message: string | null }>>;
    cancelGoogle(): Promise<IpcResult<boolean>>;
    bootstrap(): Promise<IpcResult<BootstrapResult>>;
    restore(): Promise<IpcResult<BootstrapResult>>;
    logout(): Promise<IpcResult<boolean>>;
    savedAccounts(): Promise<IpcResult<SavedAccount[]>>;
  };
  api: {
    request(request: ApiRequest): Promise<IpcResult<ApiResponse>>;
  };
  files: {
    pick(request: PickFileRequest): Promise<IpcResult<string[]>>;
    open(path: string): Promise<IpcResult<boolean>>;
    reveal(path: string): Promise<IpcResult<boolean>>;
    ensureDir(path: string): Promise<IpcResult<string>>;
    readImage(path: string): Promise<
      IpcResult<{ name: string; mime: string; bytes: Uint8Array }>
    >;
    readImageJob(request: {
      jobId: string;
      path?: string;
    }): Promise<IpcResult<{ name: string; mime: string; bytes: Uint8Array }>>;
  };
  media: {
    url(request: { path: string }): Promise<IpcResult<{ url: string }>>;
  };
  preferences: {
    getDevice(): Promise<IpcResult<DevicePreferences>>;
    setDevice(request: Partial<DevicePreferences>): Promise<IpcResult<DevicePreferences>>;
  };
  ffmpeg: {
    available(): Promise<IpcResult<{ available: boolean }>>;
    probe(request: { path: string }): Promise<IpcResult<unknown>>;
    run(request: {
      input: string;
      output: string;
      width?: number;
      height?: number;
      fps?: number;
      crf?: number;
      durationSec?: number;
    }): Promise<IpcResult<{ jobId: string }>>;
    cancel(jobId: string): Promise<IpcResult<{ cancelled: boolean }>>;
    onProgress(callback: (payload: unknown) => void): () => void;
    onDone(callback: (payload: unknown) => void): () => void;
    onFailed(callback: (payload: unknown) => void): () => void;
  };
  templates: {
    list(): Promise<IpcResult<InstalledTemplate[]>>;    install(request: InstallTemplateRequest): Promise<IpcResult<InstallTemplateResult>>;
    preview(request: { itemId: string; url: string }): Promise<IpcResult<{ dataUrl: string }>>;
    onChange(callback: (payload: TemplateChangedEvent) => void): () => void;
  };
  diagnostics: {
    send(note?: string): Promise<IpcResult<{ uploadId: string }>>;
  };
  youtube: {
    /** Merged-file + channel + quota verdict for the visible Progress rows. */
    availability(request: { rows: YoutubeUploadRowQuery[] }): Promise<IpcResult<YoutubeAvailability>>;
    /** Channel, title, visibility/schedule and playlist for the confirm dialog. */
    plan(request: { row: YoutubeUploadRowQuery }): Promise<IpcResult<YoutubeUploadPlan>>;
    start(request: YoutubeUploadStartRequest): Promise<IpcResult<YoutubeUploadState>>;
    cancel(uploadId?: string): Promise<IpcResult<{ cancelled: boolean }>>;
    state(): Promise<IpcResult<YoutubeUploadSnapshot>>;
    onChange(callback: (payload: YoutubeUploadChangedEvent) => void): () => void;
  };
  updates: {
    check(): Promise<IpcResult<UpdateCheckResult>>;
    open(offer: UpdateOffer): Promise<IpcResult<boolean>>;
  };
  videoTemplates: {
    list(): Promise<IpcResult<VideoTemplateInfo[]>>;
    read(id: string): Promise<IpcResult<VideoTemplateInfo & { pipeline: unknown }>>;
    remove(id: string): Promise<IpcResult<boolean>>;
    onChange(callback: (payload: VideoTemplateChangedEvent) => void): () => void;
  };
  downloads: {
    list(): Promise<IpcResult<DownloadSnapshot>>;
    start(): Promise<IpcResult<DownloadSnapshot>>;
    stop(): Promise<IpcResult<DownloadSnapshot>>;
    retry(key: string): Promise<IpcResult<DownloadSnapshot>>;
    cancel(key: string): Promise<IpcResult<DownloadSnapshot>>;
    reveal(key: string): Promise<IpcResult<boolean>>;
    recoverRow(request: {
      batchId: string;
      profileId: string;
      role: string;
      mode: "missing" | "change";
      runDir?: string;
      expected?: number;
      currentRunDir?: string;
    }): Promise<
      IpcResult<{ downloaded: number; skipped: number; failed: number; runDir: string }>
    >;
    onChange(callback: (payload: DownloadChangedEvent) => void): () => void;
  };
  pipeline: {
    list(): Promise<IpcResult<PipelineSnapshot>>;
    enqueue(request: PipelineEnqueueRequest): Promise<IpcResult<PipelineEnqueueResult>>;
    start(): Promise<IpcResult<{ started: boolean; running: boolean }>>;
    cancel(): Promise<IpcResult<{ cancelled: boolean; batchIds: string[] }>>;
    retry(batchId?: string): Promise<IpcResult<{ enqueued: number; started: boolean }>>;
    force(request: {
      mode: "force" | "repair" | "single";
      batchId?: string;
      jobIds?: string[];
    }): Promise<IpcResult<{ enqueued: number; started: boolean }>>;
    deleteExternal(externalBatchId: string): Promise<IpcResult<{ removed: number }>>;
    clear(): Promise<IpcResult<{ removed: number }>>;
    reveal(path: string): Promise<IpcResult<boolean>>;
    onChange(callback: (payload: PipelineChangedEvent) => void): () => void;
  };
  vizzy: {
    attach(bounds: VizzyBounds): Promise<IpcResult<VizzyState>>;
    detach(): Promise<IpcResult<boolean>>;
    setBounds(bounds: VizzyBounds): Promise<IpcResult<boolean>>;
    state(): Promise<IpcResult<VizzyState>>;
    probe(): Promise<IpcResult<VizzyProbe>>;
    reload(): Promise<IpcResult<boolean>>;
    save(): Promise<IpcResult<VizzySaveResult>>;
    open(): Promise<IpcResult<VizzyOpenResult | null>>;
    /** Start a fresh project; the shell confirms first. */
    newProject(): Promise<IpcResult<boolean>>;
    /** Live composition info (especially duration after the audio loads). */
    projectInfo(): Promise<
      IpcResult<{ name: string; width: number; height: number; fps: number; duration: number } | null>
    >;
    openPath(path: string): Promise<IpcResult<VizzyOpenResult>>;
    export(settings?: VizzyExportSettingsInput): Promise<IpcResult<VizzyExportOutcome>>;
    cancelExport(jobId: string): Promise<IpcResult<{ cancelled: boolean }>>;
    renders(): Promise<IpcResult<VizzyRenderSummary[]>>;
    deleteRender(name: string): Promise<IpcResult<{ deleted: boolean }>>;
    revealRender(name: string): Promise<IpcResult<boolean>>;
    renderUrl(name: string): Promise<IpcResult<{ url: string }>>;
    /** Hide the native editor while a shell modal is open. */
    setVisible(visible: boolean): Promise<IpcResult<boolean>>;
    /** Hide the native editor behind a transient shell overlay (notifications). */
    setObscured(obscured: boolean): Promise<IpcResult<boolean>>;
    templateOptions(): Promise<IpcResult<VizzyTemplateDraftInfo>>;
    saveTemplate(input: VizzySaveTemplateInput): Promise<IpcResult<VideoTemplateInfo>>;
    previewTemplate(id: string): Promise<IpcResult<VizzyOpenResult>>;
    openLibrary(): Promise<IpcResult<{ opened: boolean }>>;
    renderTemplate(request: VizzyRenderTemplateRequest): Promise<IpcResult<VizzyExportOutcome>>;
    onState(callback: (state: VizzyState) => void): () => void;
    onExportProgress(callback: (progress: VizzyExportProgress) => void): () => void;
  };
}

declare global {
  interface Window {
    camxora: CamxoraBridge;
  }
}

export {};
