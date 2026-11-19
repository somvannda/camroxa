/**
 * Skeleton bridge for the hosted Vizzy editor.
 *
 * SELF-CONTAINED BY DESIGN: nothing imports this file yet. The P7 integration
 * will create one bridge per Vizzy `WebContentsView`, register a dedicated
 * preload channel and pass real handlers (project store, native dialogs,
 * `camxora-media://`, FFmpeg). See `docs/electron-desktop/vizzy/HOST-SPIKE.md`
 * and `02-MODULE-MAP.md` §3.1/§4.3.
 *
 * Shape:
 *
 *   view preload  --ipcRenderer.send("vizzy:bridge", msg)-->  ipcMain
 *   ipcMain       --bridge.handleViewMessage(msg)--------->   handlers
 *   bridge        --webContents.send("vizzy:bridge", msg)-->  view preload
 *   view preload  ------------------------------------------>  window.camxoraVizzy
 *
 * Binary payloads are `ArrayBuffer` (structured clone), never base64.
 */
import type { WebContents } from "electron";

export const VIZZY_BRIDGE_VERSION = 1;
export const VIZZY_BRIDGE_CHANNEL = "vizzy:bridge";

export type VizzyMediaKind = "image" | "video" | "audio";

/** Mirrors the module-map `ProjectSummary` without committing to SQLite yet. */
export interface VizzyProjectSummary {
  id: string;
  name: string;
  path?: string;
  updatedAt: number;
  thumbnailPath?: string;
}

export interface VizzyExportOptions {
  format: "mp4" | "webm";
  width: number;
  height: number;
  fps: number;
  durationSec: number;
  audioPath?: string;
  outputPath?: string;
}

export interface VizzyOpenedProject {
  id?: string;
  name: string;
  bytes: ArrayBuffer;
}

/** view -> host */
export type VizzyViewMessage =
  | { v: 1; type: "vizzy:ready" }
  | { v: 1; type: "vizzy:dirty"; dirty: boolean }
  | {
      v: 1;
      type: "vizzy:state";
      state: {
        ready: boolean;
        projectName: string;
        dirty: boolean;
        nodeCount: number;
        projectWidth?: number;
        projectHeight?: number;
        projectFps?: number;
        projectDuration?: number;
        crossOriginIsolated: boolean;
        fftTier: string;
      };
    }
  | { v: 1; type: "vizzy:ack"; requestId: string; ok: boolean; error?: string }
  | { v: 1; type: "vizzy:save"; name: string; bytes: ArrayBuffer }
  | { v: 1; type: "vizzy:open" }
  | { v: 1; type: "vizzy:pick-media"; kind: VizzyMediaKind }
  | { v: 1; type: "vizzy:export"; request: VizzyExportOptions }
  | { v: 1; type: "vizzy:cancel-export"; jobId: string }
  | {
      v: 1;
      type: "vizzy:export-progress";
      jobId: string;
      done: number;
      total: number;
      stage: string;
    }
  | {
      v: 1;
      type: "vizzy:export-finished";
      jobId: string;
      ok: boolean;
      cancelled: boolean;
      frames: number;
      error?: string;
    }
  | { v: 1; type: "vizzy:log"; level: VizzyLogLevel; message: string; detail?: unknown }
  | { v: 1; type: "vizzy:error"; message: string; stack?: string };

/** host -> view */
export type VizzyHostMessage =
  | {
      v: 1;
      type: "vizzy:init";
      tokens: Record<string, string>;
      app: { version: string; env: string };
      project: VizzyProjectSummary | null;
    }
  | { v: 1; type: "vizzy:theme"; tokens: Record<string, string> }
  | { v: 1; type: "vizzy:open-project"; project: VizzyOpenedProject }
  | {
      /** P7 native open: the editor's snapshot travels as JSON, not bytes. */
      v: 1;
      type: "vizzy:open-project-json";
      requestId: string;
      path: string;
      name: string;
      json: string;
    }
  | { v: 1; type: "vizzy:project-saved"; path: string }
  | { v: 1; type: "vizzy:media-picked"; kind: VizzyMediaKind; url: string }
  | {
      /** Host-driven export: the editor runs its own exporter for this job. */
      v: 1;
      type: "vizzy:export-run";
      jobId: string;
      settings: {
        width: number;
        height: number;
        fps: number;
        format: "mp4" | "webm";
        codec: "h264" | "vp8" | "vp9";
        bitrate: number;
        crf: number;
        start: number;
        end: number;
      };
    }
  | { v: 1; type: "vizzy:export-cancel"; jobId: string }
  | { v: 1; type: "vizzy:error"; message: string };

export type VizzyLogLevel = "debug" | "info" | "warn" | "error";

/**
 * Native capabilities the shell supplies. Every method returns view-safe data
 * only: opaque project ids, ready-to-use `camxora-media://` URLs, job ids.
 * No absolute path is handed to the renderer unless it is an export output
 * the user explicitly chose.
 */
export interface VizzyBridgeHandlers {
  saveProject(input: { name: string; bytes: ArrayBuffer }): Promise<{ path: string } | null>;
  openProject(): Promise<VizzyOpenedProject | null>;
  /** Returns a `camxora-media://` URL, or null when the picker was cancelled. */
  pickMedia(kind: VizzyMediaKind): Promise<string | null>;
  startExport(request: VizzyExportOptions): Promise<{ jobId: string }>;
  cancelExport(jobId: string): Promise<boolean>;
  appInfo(): Promise<{ version: string; env: string }>;
  log(level: VizzyLogLevel, message: string, detail?: unknown): void;
}

export interface VizzyBridgeOptions {
  contents: WebContents;
  handlers: VizzyBridgeHandlers;
  /** Theme tokens pushed with `vizzy:init`. */
  tokens?: Record<string, string>;
  /** Project shown after the view reports ready. */
  project?: VizzyProjectSummary | null;
  /** Save-state strip in the shell; wired to the same store as `vizzy:dirty`. */
  onDirty?: (dirty: boolean) => void;
  /** Richer strip state: project name, node count and FFT tier. */
  onState?: (state: {
    ready: boolean;
    projectName: string;
    dirty: boolean;
    nodeCount: number;
    projectWidth?: number;
    projectHeight?: number;
    projectFps?: number;
    projectDuration?: number;
    crossOriginIsolated: boolean;
    fftTier: string;
  }) => void;
  /** Acknowledgement for an `open-project-json` command. */
  onAck?: (payload: { requestId: string; ok: boolean; error?: string }) => void;
  /** Progress the editor reports while the host-driven export runs. */
  onExportProgress?: (payload: {
    jobId: string;
    done: number;
    total: number;
    stage: string;
  }) => void;
  /** The editor's exporter finished; the host validates and settles the job. */
  onExportFinished?: (payload: {
    jobId: string;
    ok: boolean;
    cancelled: boolean;
    frames: number;
    error?: string;
  }) => void;
}

export interface VizzyBridge {
  /** Call from `ipcMain.on(VIZZY_BRIDGE_CHANNEL, (_event, message) => …)`. */
  handleViewMessage(message: unknown): Promise<void>;
  send(message: VizzyHostMessage): void;
  dispose(): void;
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}

export function createVizzyBridge(options: VizzyBridgeOptions): VizzyBridge {
  const { contents, handlers } = options;
  let disposed = false;

  const send = (message: VizzyHostMessage): void => {
    if (disposed || contents.isDestroyed()) return;
    contents.send(VIZZY_BRIDGE_CHANNEL, message);
  };

  const fail = (message: string): void => {
    send({ v: 1, type: "vizzy:error", message });
  };

  async function handleViewMessage(raw: unknown): Promise<void> {
    if (disposed) return;
    if (!isRecord(raw) || raw.v !== VIZZY_BRIDGE_VERSION || typeof raw.type !== "string") {
      fail("Unsupported bridge message");
      return;
    }

    try {
      switch (raw.type) {
        case "vizzy:ready": {
          const app = await handlers.appInfo();
          send({
            v: 1,
            type: "vizzy:init",
            tokens: options.tokens ?? {},
            app,
            project: options.project ?? null,
          });
          return;
        }
        case "vizzy:dirty": {
          const dirty = raw.dirty === true;
          options.onDirty?.(dirty);
          return;
        }
        case "vizzy:state": {
          if (!isRecord(raw.state)) {
            fail("Invalid state payload");
            return;
          }
          const state = raw.state;
          options.onState?.({
            ready: state.ready === true,
            projectName: typeof state.projectName === "string" ? state.projectName : "",
            dirty: state.dirty === true,
            nodeCount: typeof state.nodeCount === "number" ? state.nodeCount : 0,
            projectWidth: typeof state.projectWidth === "number" ? state.projectWidth : 0,
            projectHeight: typeof state.projectHeight === "number" ? state.projectHeight : 0,
            projectFps: typeof state.projectFps === "number" ? state.projectFps : 0,
            projectDuration: typeof state.projectDuration === "number" ? state.projectDuration : 0,
            crossOriginIsolated: state.crossOriginIsolated === true,
            fftTier: typeof state.fftTier === "string" ? state.fftTier : "unknown",
          });
          return;
        }
        case "vizzy:ack": {
          if (typeof raw.requestId !== "string") {
            fail("Invalid acknowledgement");
            return;
          }
          options.onAck?.({
            requestId: raw.requestId,
            ok: raw.ok === true,
            error: typeof raw.error === "string" ? raw.error : undefined,
          });
          return;
        }
        case "vizzy:save": {
          if (typeof raw.name !== "string" || !(raw.bytes instanceof ArrayBuffer)) {
            fail("Invalid save payload");
            return;
          }
          const saved = await handlers.saveProject({ name: raw.name, bytes: raw.bytes });
          if (saved) send({ v: 1, type: "vizzy:project-saved", path: saved.path });
          return;
        }
        case "vizzy:open": {
          const opened = await handlers.openProject();
          if (opened) send({ v: 1, type: "vizzy:open-project", project: opened });
          return;
        }
        case "vizzy:pick-media": {
          const kind = raw.kind;
          if (kind !== "image" && kind !== "video" && kind !== "audio") {
            fail("Invalid media kind");
            return;
          }
          const url = await handlers.pickMedia(kind);
          if (url) send({ v: 1, type: "vizzy:media-picked", kind, url });
          return;
        }
        case "vizzy:export": {
          if (!isRecord(raw.request)) {
            fail("Invalid export request");
            return;
          }
          // The host's `startExport` refuses view-originated jobs: the shell owns
          // the destination file, progress and cancellation. Kept for protocol
          // compatibility with the pre-host editor bridge.
          const { jobId } = await handlers.startExport(raw.request as unknown as VizzyExportOptions);
          if (!jobId) fail("Export did not return a job id");
          return;
        }
        case "vizzy:cancel-export": {
          if (typeof raw.jobId !== "string") {
            fail("Invalid export job id");
            return;
          }
          await handlers.cancelExport(raw.jobId);
          return;
        }
        case "vizzy:export-progress": {
          if (typeof raw.jobId !== "string") {
            fail("Invalid export progress");
            return;
          }
          options.onExportProgress?.({
            jobId: raw.jobId,
            done: Number(raw.done) || 0,
            total: Number(raw.total) || 0,
            stage: typeof raw.stage === "string" ? raw.stage : "",
          });
          return;
        }
        case "vizzy:export-finished": {
          if (typeof raw.jobId !== "string") {
            fail("Invalid export result");
            return;
          }
          options.onExportFinished?.({
            jobId: raw.jobId,
            ok: raw.ok === true,
            cancelled: raw.cancelled === true,
            frames: Number(raw.frames) || 0,
            error: typeof raw.error === "string" ? raw.error : undefined,
          });
          return;
        }
        case "vizzy:log": {
          const level = raw.level;
          if (level !== "debug" && level !== "info" && level !== "warn" && level !== "error") return;
          handlers.log(level, String(raw.message ?? ""), raw.detail);
          return;
        }
        case "vizzy:error": {
          handlers.log("error", String(raw.message ?? "unknown view error"), raw.stack);
          return;
        }
        default:
          fail(`Unknown bridge message: ${raw.type}`);
      }
    } catch (error) {
      handlers.log("error", "bridge handler failed", {
        type: raw.type,
        error: error instanceof Error ? error.message : String(error),
      });
      fail(error instanceof Error ? error.message : "Bridge handler failed");
    }
  }

  return {
    handleViewMessage,
    send,
    dispose(): void {
      disposed = true;
    },
  };
}
