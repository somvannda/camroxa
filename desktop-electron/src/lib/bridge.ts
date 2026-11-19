import type {
  ApiRequest,
  ApiResponse,
  AppInfo,
  BootstrapResult,
  IpcResult,
  PickFileRequest,
  SavedAccount,
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
  };
  media: {
    url(request: { path: string }): Promise<IpcResult<{ url: string }>>;
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
  diagnostics: {
    send(note?: string): Promise<IpcResult<{ uploadId: string }>>;
  };
}

declare global {
  interface Window {
    camxora: CamxoraBridge;
  }
}

export {};
