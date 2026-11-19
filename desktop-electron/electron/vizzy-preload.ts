/**
 * Dedicated preload for the hosted Vizzy editor.
 *
 * The view runs with `contextIsolation: true`, `sandbox: true` and
 * `nodeIntegration: false`. This file injects exactly one object —
 * `window.camxoraVizzy` — and nothing else: no `ipcRenderer`, no `fs`, no shell
 * bridge. Every channel it touches is validated on the main side against the
 * view's own webContents id.
 *
 * Contract: `vizzy/patches/bridge.ts` (vendored into `vizzy/src/host/bridge.ts`).
 */
import { contextBridge, ipcRenderer } from "electron";

const BRIDGE_CHANNEL = "vizzy:bridge";

interface VizzyHostState {
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

interface VizzySavedProject {
  path: string;
  name: string;
}

interface VizzyOpenedProject {
  path: string;
  name: string;
  json: string;
}

interface VizzyExportSettings {
  width: number;
  height: number;
  fps: number;
  format: "mp4" | "webm";
  codec: "h264" | "vp8" | "vp9";
  bitrate: number;
  crf: number;
  start: number;
  end: number;
}

type VizzyHostCommand =
  | {
      v: 1;
      type: "open-project";
      requestId: string;
      path: string;
      name: string;
      json: string;
    }
  | { v: 1; type: "project-saved"; path: string; name: string }
  | { v: 1; type: "load-audio"; requestId: string; name: string; url: string }
  | { v: 1; type: "export-run"; jobId: string; settings: VizzyExportSettings }
  | { v: 1; type: "export-cancel"; jobId: string };

interface HostMessage {
  v?: number;
  type?: string;
  requestId?: string;
  path?: string;
  name?: string;
  url?: string;
  json?: string;
  jobId?: string;
  settings?: Partial<VizzyExportSettings>;
}

function number(value: unknown, fallback: number): number {
  return typeof value === "number" && Number.isFinite(value) ? value : fallback;
}

function toCommand(message: HostMessage): VizzyHostCommand | null {
  if (message.v !== 1) return null;
  if (message.type === "vizzy:open-project-json") {
    if (
      typeof message.requestId !== "string" ||
      typeof message.path !== "string" ||
      typeof message.name !== "string" ||
      typeof message.json !== "string"
    ) {
      return null;
    }
    return {
      v: 1,
      type: "open-project",
      requestId: message.requestId,
      path: message.path,
      name: message.name,
      json: message.json,
    };
  }
  if (message.type === "vizzy:project-saved" && typeof message.path === "string") {
    return { v: 1, type: "project-saved", path: message.path, name: "" };
  }
  if (message.type === "vizzy:load-audio") {
    if (
      typeof message.requestId !== "string" ||
      typeof message.name !== "string" ||
      typeof message.url !== "string"
    ) {
      return null;
    }
    return {
      v: 1,
      type: "load-audio",
      requestId: message.requestId,
      name: message.name,
      url: message.url,
    };
  }
  if (message.type === "vizzy:export-run" && typeof message.jobId === "string") {
    const settings = message.settings ?? {};
    return {
      v: 1,
      type: "export-run",
      jobId: message.jobId,
      settings: {
        width: number(settings.width, 1920),
        height: number(settings.height, 1080),
        fps: number(settings.fps, 30),
        format: settings.format === "webm" ? "webm" : "mp4",
        codec:
          settings.codec === "vp8" || settings.codec === "vp9" ? settings.codec : "h264",
        bitrate: number(settings.bitrate, 0),
        crf: number(settings.crf, 20),
        start: number(settings.start, 0),
        end: number(settings.end, 0),
      },
    };
  }
  if (message.type === "vizzy:export-cancel" && typeof message.jobId === "string") {
    return { v: 1, type: "export-cancel", jobId: message.jobId };
  }
  return null;
}

const bridge = {
  version: 1 as const,
  platform: "camxora-desktop" as const,

  saveProject(name: string, json: string): Promise<VizzySavedProject | null> {
    return ipcRenderer.invoke("vizzy:project:save", { name, json }) as Promise<VizzySavedProject | null>;
  },

  openProject(): Promise<VizzyOpenedProject | null> {
    return ipcRenderer.invoke("vizzy:project:open") as Promise<VizzyOpenedProject | null>;
  },

  notifyDirty(dirty: boolean): void {
    ipcRenderer.send(BRIDGE_CHANNEL, { v: 1, type: "vizzy:dirty", dirty: dirty === true });
  },

  reportState(state: VizzyHostState): void {
    ipcRenderer.send(BRIDGE_CHANNEL, { v: 1, type: "vizzy:state", state });
  },

  acknowledge(payload: { requestId: string; ok: boolean; error?: string }): void {
    ipcRenderer.send(BRIDGE_CHANNEL, {
      v: 1,
      type: "vizzy:ack",
      requestId: payload.requestId,
      ok: payload.ok === true,
      ...(payload.error ? { error: payload.error } : {}),
    });
  },

  /* Native export ---------------------------------------------------- */

  /** One encoder chunk, written by the host at its absolute file offset. */
  async exportChunk(
    jobId: string,
    position: number,
    data: Uint8Array,
  ): Promise<{ bytes: number }> {
    const result = (await ipcRenderer.invoke("vizzy:export:chunk", {
      jobId,
      position,
      data,
    })) as { ok: true; data: { bytes: number } } | { ok: false; error: { message: string } };
    if (!result || result.ok !== true) {
      throw new Error(result && !result.ok ? result.error.message : "The host rejected that render chunk.");
    }
    return result.data;
  },

  exportProgress(payload: { jobId: string; done: number; total: number; stage: string }): void {
    ipcRenderer.send(BRIDGE_CHANNEL, {
      v: 1,
      type: "vizzy:export-progress",
      jobId: payload.jobId,
      done: payload.done,
      total: payload.total,
      stage: payload.stage,
    });
  },

  exportFinished(payload: {
    jobId: string;
    ok: boolean;
    cancelled: boolean;
    frames: number;
    error?: string;
  }): void {
    ipcRenderer.send(BRIDGE_CHANNEL, {
      v: 1,
      type: "vizzy:export-finished",
      jobId: payload.jobId,
      ok: payload.ok === true,
      cancelled: payload.cancelled === true,
      frames: Math.max(0, Math.round(Number(payload.frames) || 0)),
      ...(payload.error ? { error: payload.error.slice(0, 400) } : {}),
    });
  },

  onCommand(handler: (command: VizzyHostCommand) => void): () => void {
    const listener = (_event: unknown, message: HostMessage) => {
      const command = toCommand(message ?? {});
      if (command) handler(command);
    };
    ipcRenderer.on(BRIDGE_CHANNEL, listener);
    return () => {
      ipcRenderer.removeListener(BRIDGE_CHANNEL, listener);
    };
  },
};

contextBridge.exposeInMainWorld("camxoraVizzy", bridge);
