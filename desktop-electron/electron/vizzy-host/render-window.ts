/**
 * Offscreen Vizzy render host.
 *
 * A hidden `BrowserWindow` loads the same editor bundle from
 * `camxora-vizzy://vizzy/index.html` with the same sandboxed preload, waits for
 * the editor's ready probe, applies a project JSON (a saved template with the
 * run's bindings), streams the run audio over `camxora-media://` and runs the
 * editor's own exporter into a host-backed file.
 *
 * Why a window and not the visible `WebContentsView`: a queued job must render
 * whether or not the user is on `/vizzy`. The window uses a dedicated session
 * partition, so autosave / local editor state can never collide with the
 * visible editor's.
 *
 * Security: no Node, context isolation, sandbox, and only the editor origin may
 * be loaded. The page reaches the main process through the same validated
 * bridge as the visible editor.
 */
import crypto from "node:crypto";
import fs from "node:fs";
import path from "node:path";
import { BrowserWindow, shell, type WebContents } from "electron";
import type { VizzyExportOutcome, VizzyExportProgress, VizzyExportSettingsInput } from "../shared/types";
import { logger } from "../services/logger";
import { allowPickedFile, createMediaUrl } from "../services/media";
import { VIZZY_INDEX_URL } from "./assets";
import { createVizzyBridge, type VizzyBridge } from "./bridge";
import { VizzyExportSession } from "./export-session";

/** Dedicated partition: never shares storage with the visible editor. */
export const VIZZY_RENDER_PARTITION = "vizzy-render";

const READY_TIMEOUT_MS = 90_000;
const READY_POLL_MS = 120;
const ACK_TIMEOUT_MS = 30_000;
const AUDIO_ACK_TIMEOUT_MS = 180_000;

const VIZZY_ORIGIN = new URL(VIZZY_INDEX_URL).origin;

export interface OffscreenRenderDeps {
  /** `dist-electron/vizzy-preload.cjs`. */
  preloadPath: string;
  /** Managed `renders/` directory. */
  rendersDir: string;
  /** Shell-facing progress (same event as the visible export). */
  onExportProgress?: (progress: VizzyExportProgress) => void;
}

export interface OffscreenRenderRequest {
  /** The saved template with the run bindings applied. */
  projectJson: string;
  /** Project name shown in the editor (never a path). */
  name: string;
  audioPath: string;
  settings: VizzyExportSettingsInput;
  /** Output stem; the host adds the timestamp and extension. */
  outputName: string;
  onProgress?: (progress: VizzyExportProgress) => void;
  onStarted?: (jobId: string) => void;
  /** Checked after the project and audio are loaded, before the export runs. */
  shouldAbort?: () => boolean;
}

interface PendingAck {
  resolve: (result: { ok: boolean; error?: string }) => void;
  timer: NodeJS.Timeout;
}

export class OffscreenVizzyRenderer {
  private window: BrowserWindow | null = null;
  private bridge: VizzyBridge | null = null;
  private readonly session: VizzyExportSession;
  private pendingAcks = new Map<string, PendingAck>();
  private ready = false;
  private loading: Promise<void> | null = null;
  private disposed = false;
  private lastError: string | null = null;
  private progressListener: ((progress: VizzyExportProgress) => void) | null = null;

  constructor(private readonly deps: OffscreenRenderDeps) {
    this.session = new VizzyExportSession({
      rendersDir: deps.rendersDir,
      getContents: () => this.contents(),
      getBridge: () => this.bridge,
      isReady: () => this.ready,
      defaultName: () => "batch-render",
      getProjectInfo: () => this.readProjectInfo(),
      onProgress: (progress) => this.emitProgress(progress),
    });
  }

  /** True only for this window's webContents (channel guard). */
  isSender(sender: WebContents): boolean {
    const contents = this.contents();
    return Boolean(contents && !contents.isDestroyed() && contents.id === sender.id);
  }

  hasWindow(): boolean {
    const contents = this.contents();
    return Boolean(contents && !contents.isDestroyed());
  }

  get lastErrorText(): string | null {
    return this.lastError;
  }

  get currentJobId(): string | null {
    return this.session.currentJobId;
  }

  /** Create the hidden window (once) and wait until the editor reports ready. */
  async ensureReady(): Promise<void> {
    if (this.disposed) throw new Error("The batch renderer has been closed.");
    if (this.ready && this.hasWindow()) return;
    if (this.loading) return this.loading;

    this.loading = this.startWindow().finally(() => {
      this.loading = null;
    });
    return this.loading;
  }

  /** Apply a project JSON and load the run audio; the window must be ready. */
  async prepare(input: {
    projectJson: string;
    name: string;
    audioPath: string;
  }): Promise<void> {
    await this.ensureReady();
    await this.openProject(input.projectJson, input.name);
    await this.loadAudio(input.audioPath);
  }

  /** Prepare and export one render. */
  async render(request: OffscreenRenderRequest): Promise<VizzyExportOutcome> {
    await this.prepare({
      projectJson: request.projectJson,
      name: request.name,
      audioPath: request.audioPath,
    });
    // A cancel during loading must not start an export that would leave a file.
    if (request.shouldAbort?.()) return { status: "cancelled" };
    const previous = this.progressListener;
    this.progressListener = request.onProgress ?? null;
    try {
      return await this.session.start(request.settings, {
        outputName: request.outputName,
        onStarted: request.onStarted,
      });
    } finally {
      this.progressListener = previous;
    }
  }

  handleViewMessage(message: unknown): Promise<void> {
    return this.bridge?.handleViewMessage(message) ?? Promise.resolve();
  }

  writeChunk(input: { jobId: string; position: number; data: Uint8Array }): Promise<{ bytes: number }> {
    return this.session.writeChunk(input);
  }

  cancel(jobId: string): boolean {
    return this.session.cancel(jobId);
  }

  handleProgress(payload: { jobId: string; done: number; total: number; stage: string }): void {
    this.session.handleProgress(payload);
  }

  handleFinished(payload: {
    jobId: string;
    ok: boolean;
    cancelled: boolean;
    frames: number;
    error?: string;
  }): Promise<void> {
    return this.session.handleFinished(payload);
  }

  /** Close the window. Never deletes a user file; the export session cleans up. */
  dispose(): void {
    this.disposed = true;
    this.clearPendingAcks("The batch renderer was closed.");
    this.session.abort("The batch renderer is closing.");
    this.destroyWindow();
  }

  /* ------------------------------------------------------------------ */

  private emitProgress(progress: VizzyExportProgress): void {
    this.deps.onExportProgress?.(progress);
    this.progressListener?.(progress);
  }

  private contents(): WebContents | null {
    const window = this.window;
    if (!window || window.isDestroyed()) return null;
    const contents = window.webContents;
    return contents.isDestroyed() ? null : contents;
  }

  private async startWindow(): Promise<void> {
    const window = this.createWindow();
    try {
      await contentsLoad(window.webContents);
      await this.waitForReady();
    } catch (error) {
      this.lastError = error instanceof Error ? error.message : String(error);
      logger.error("vizzy render host failed to start", { error: this.lastError });
      this.destroyWindow();
      throw error;
    }
  }

  private createWindow(): BrowserWindow {
    this.lastError = null;
    const window = new BrowserWindow({
      show: false,
      width: 1280,
      height: 720,
      frame: false,
      skipTaskbar: true,
      backgroundColor: "#070a13",
      title: "Camxora renderer",
      webPreferences: {
        preload: this.deps.preloadPath,
        contextIsolation: true,
        sandbox: true,
        nodeIntegration: false,
        webSecurity: true,
        spellcheck: false,
        // A hidden window still paints and runs rAF; throttling would stretch
        // a 30 fps export into a slideshow.
        backgroundThrottling: false,
        partition: VIZZY_RENDER_PARTITION,
      },
    });
    window.setMenuBarVisibility(false);
    this.window = window;
    this.ready = false;

    const contents = window.webContents;

    contents.setWindowOpenHandler(({ url }) => {
      if (/^https?:\/\//i.test(url)) void shell.openExternal(url);
      return { action: "deny" };
    });

    contents.on("will-navigate", (event, url) => {
      if (url !== VIZZY_INDEX_URL && !url.startsWith(`${VIZZY_ORIGIN}/`)) {
        event.preventDefault();
        if (/^https?:\/\//i.test(url)) void shell.openExternal(url);
      }
    });

    contents.on("render-process-gone", (_event, details) => {
      logger.error("vizzy render host process gone", { reason: details.reason });
      this.ready = false;
      this.lastError = `The batch renderer stopped responding (${details.reason}).`;
      this.session.abort("The batch renderer stopped responding.");
      this.window = null;
      try {
        if (!window.isDestroyed()) window.destroy();
      } catch {
        /* already gone */
      }
    });

    contents.on("did-fail-load", (_event, code, description, url) => {
      if (code === -3) return;
      logger.error("vizzy render host load failed", { code, description, url });
      this.ready = false;
      this.lastError = `The batch renderer failed to load the editor (${description}).`;
    });

    contents.on("console-message", (_event, level, message, line, sourceId) => {
      if (level >= 2) logger.warn("vizzy render console", { message, line, sourceId });
    });

    this.bridge = createVizzyBridge({
      contents,
      handlers: {
        // The render window never saves or opens projects through dialogs; the
        // pipeline supplies the exact snapshot it wants rendered.
        saveProject: async () => null,
        openProject: async () => null,
        pickMedia: async () => null,
        startExport: async () => {
          throw new Error("Start exports from the Camxora pipeline.");
        },
        cancelExport: async () => false,
        appInfo: async () => ({ version: "2.0.0", env: process.env.NODE_ENV ?? "production" }),
        log: (level, message, detail) => {
          const write = level === "warn" ? logger.warn : level === "error" ? logger.error : logger.info;
          write("vizzy render host", { message, detail });
        },
      },
      onAck: (payload) => this.resolveAck(payload),
      onExportProgress: (payload) => this.session.handleProgress(payload),
      onExportFinished: (payload) => void this.session.handleFinished(payload),
    });

    return window;
  }

  private async waitForReady(): Promise<void> {
    const deadline = Date.now() + READY_TIMEOUT_MS;
    for (;;) {
      if (this.disposed) throw new Error("The batch renderer was closed.");
      const contents = this.contents();
      if (!contents) throw new Error(this.lastError ?? "The batch renderer window closed.");
      const value: unknown = await contents
        .executeJavaScript("Boolean(window.__vizzyTest && window.__vizzyTest.ready)", true)
        .catch(() => false);
      if (value === true) {
        this.ready = true;
        return;
      }
      if (Date.now() > deadline) {
        throw new Error("The batch renderer did not finish loading the editor.");
      }
      await delay(READY_POLL_MS);
    }
  }

  private async openProject(json: string, name: string): Promise<void> {
    const bridge = this.bridge;
    if (!bridge) throw new Error("The batch renderer is not ready.");
    const requestId = crypto.randomUUID();
    const ack = this.waitForAck(requestId);
    bridge.send({
      v: 1,
      type: "vizzy:open-project-json",
      requestId,
      path: "",
      name,
      json,
    });
    const result = await ack;
    if (!result.ok) throw new Error(result.error ?? "The editor could not open that template.");
  }

  private async loadAudio(filePath: string): Promise<void> {
    const bridge = this.bridge;
    if (!bridge) throw new Error("The batch renderer is not ready.");
    const resolved = path.resolve(filePath);
    let stat: fs.Stats;
    try {
      stat = fs.statSync(resolved);
    } catch {
      throw new Error(`The audio file does not exist: ${resolved}`);
    }
    if (!stat.isFile()) throw new Error("The audio path is not a file.");
    if (stat.size <= 0) throw new Error("The audio file is empty.");
    allowPickedFile(resolved);
    const url = createMediaUrl(resolved);
    const requestId = crypto.randomUUID();
    const ack = this.waitForAck(requestId, AUDIO_ACK_TIMEOUT_MS);
    bridge.send({
      v: 1,
      type: "vizzy:load-audio",
      requestId,
      name: path.basename(resolved),
      url,
    });
    const result = await ack;
    if (!result.ok) throw new Error(result.error ?? "The editor could not load the run audio.");
  }

  private async readProjectInfo(): Promise<{
    name: string;
    width: number;
    height: number;
    fps: number;
    duration: number;
  } | null> {
    const contents = this.contents();
    if (!contents) return null;
    const script = `(() => {
      const test = window.__vizzyTest;
      if (!test || typeof test.readProjectInfo !== "function") return null;
      try { return test.readProjectInfo(); } catch { return null; }
    })()`;
    const value: unknown = await Promise.race([
      contents.executeJavaScript(script, true),
      delay(3_000).then(() => null),
    ]);
    if (!value || typeof value !== "object") return null;
    const record = value as Record<string, unknown>;
    const number = (input: unknown): number =>
      typeof input === "number" && Number.isFinite(input) ? input : 0;
    return {
      name: typeof record.name === "string" ? record.name : "",
      width: number(record.width),
      height: number(record.height),
      fps: number(record.fps),
      duration: number(record.duration),
    };
  }

  private waitForAck(
    requestId: string,
    timeoutMs = ACK_TIMEOUT_MS,
  ): Promise<{ ok: boolean; error?: string }> {
    return new Promise((resolve) => {
      const timer = setTimeout(() => {
        this.pendingAcks.delete(requestId);
        resolve({ ok: false, error: "The batch renderer did not confirm the editor command." });
      }, timeoutMs);
      this.pendingAcks.set(requestId, { resolve, timer });
    });
  }

  private resolveAck(payload: { requestId: string; ok: boolean; error?: string }): void {
    const pending = this.pendingAcks.get(payload.requestId);
    if (!pending) return;
    clearTimeout(pending.timer);
    this.pendingAcks.delete(payload.requestId);
    pending.resolve({ ok: payload.ok, error: payload.error });
  }

  private clearPendingAcks(reason: string): void {
    for (const [, pending] of this.pendingAcks) {
      clearTimeout(pending.timer);
      pending.resolve({ ok: false, error: reason });
    }
    this.pendingAcks.clear();
  }

  private destroyWindow(): void {
    this.ready = false;
    this.bridge?.dispose();
    this.bridge = null;
    const window = this.window;
    this.window = null;
    if (!window || window.isDestroyed()) return;
    try {
      window.destroy();
    } catch {
      /* already destroyed */
    }
  }
}

function delay(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

async function contentsLoad(contents: WebContents): Promise<void> {
  await contents.loadURL(VIZZY_INDEX_URL);
}
