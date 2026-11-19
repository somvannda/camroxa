import type {
  ApiRequest,
  ApiResponse,
  AppInfo,
  BootstrapResult,
  DevicePreferences,
  InstallTemplateRequest,
  InstallTemplateResult,
  InstalledTemplate,
  IpcResult,
  PickFileRequest,
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
  vizzy: {
    attach(bounds: VizzyBounds): Promise<IpcResult<VizzyState>>;
    detach(): Promise<IpcResult<boolean>>;
    setBounds(bounds: VizzyBounds): Promise<IpcResult<boolean>>;
    state(): Promise<IpcResult<VizzyState>>;
    probe(): Promise<IpcResult<VizzyProbe>>;
    reload(): Promise<IpcResult<boolean>>;
    save(): Promise<IpcResult<VizzySaveResult>>;
    open(): Promise<IpcResult<VizzyOpenResult | null>>;
    openPath(path: string): Promise<IpcResult<VizzyOpenResult>>;
    export(settings?: VizzyExportSettingsInput): Promise<IpcResult<VizzyExportOutcome>>;
    cancelExport(jobId: string): Promise<IpcResult<{ cancelled: boolean }>>;
    renders(): Promise<IpcResult<VizzyRenderSummary[]>>;
    deleteRender(name: string): Promise<IpcResult<{ deleted: boolean }>>;
    revealRender(name: string): Promise<IpcResult<boolean>>;
    renderUrl(name: string): Promise<IpcResult<{ url: string }>>;
    /** Hide the native editor while a shell modal is open. */
    setVisible(visible: boolean): Promise<IpcResult<boolean>>;
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
