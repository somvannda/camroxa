/**
 * CAMXORA host bridge contract for the hosted editor.
 *
 * `electron/vizzy-preload.ts` injects this object as `window.camxoraVizzy` in the
 * Vizzy `WebContentsView`. It is the only native surface the editor can reach:
 * no Node module, no `ipcRenderer`, no shell bridge (`window.camxora`).
 *
 * `scripts/sync-vizzy.mjs` copies this file to `src/host/bridge.ts`; edit the
 * copy under `vizzy/patches/`, never the generated one.
 */

export interface VizzyHostState {
  ready: boolean;
  projectName: string;
  dirty: boolean;
  nodeCount: number;
  projectWidth: number;
  projectHeight: number;
  projectFps: number;
  projectDuration: number;
  crossOriginIsolated: boolean;
  fftTier: string;
}

export interface VizzySavedProject {
  path: string;
  name: string;
}

export interface VizzyOpenedProject {
  path: string;
  name: string;
  json: string;
}

/** Defaults the host resolves against when the project has no settings. */
export interface VizzyProjectInfo {
  name: string;
  width: number;
  height: number;
  fps: number;
  duration: number;
}

export interface VizzyExportSettings {
  width: number;
  height: number;
  fps: number;
  format: "mp4" | "webm";
  codec: "h264" | "vp8" | "vp9";
  /** Video bitrate in Mbps; 0 lets the encoder choose a CRF. */
  bitrate: number;
  crf: number;
  start: number;
  end: number;
}

/** host -> view commands. */
export type VizzyHostCommand =
  | {
      v: 1;
      type: "open-project";
      requestId: string;
      path: string;
      name: string;
      json: string;
    }
  | { v: 1; type: "project-saved"; path: string; name: string }
  | {
      v: 1;
      type: "load-audio";
      requestId: string;
      name: string;
      url: string;
    }
  | { v: 1; type: "request-reload" }
  | { v: 1; type: "export-run"; jobId: string; settings: VizzyExportSettings }
  | { v: 1; type: "export-cancel"; jobId: string };

export interface VizzyHostBridge {
  readonly version: 1;
  readonly platform: "camxora-desktop";
  /** Persist the current project snapshot through the native project store. */
  saveProject(name: string, json: string): Promise<VizzySavedProject | null>;
  /** Ask the host for the native Open dialog and apply the picked project. */
  openProject(): Promise<VizzyOpenedProject | null>;
  /** Save-state strip: the editor reports its own dirty flag. */
  notifyDirty(dirty: boolean): void;
  /** Shell strip: name, dirty flag, node count and FFT tier. */
  reportState(state: VizzyHostState): void;
  /** Acknowledge an `open-project` command after it has been applied. */
  acknowledge(payload: { requestId: string; ok: boolean; error?: string }): void;
  /**
   * Native export: one encoded chunk at its absolute file offset. The host
   * writes it and resolves with the number of bytes written so far.
   */
  exportChunk(jobId: string, position: number, data: Uint8Array): Promise<{ bytes: number }>;
  /** Native export: progress for the shell strip. */
  exportProgress(payload: { jobId: string; done: number; total: number; stage: string }): void;
  /** Native export: terminal signal; the host validates the file and settles. */
  exportFinished(payload: {
    jobId: string;
    ok: boolean;
    cancelled: boolean;
    frames: number;
    error?: string;
  }): void;
  onCommand(handler: (command: VizzyHostCommand) => void): () => void;
}
