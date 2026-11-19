/**
 * Production host for the Vizzy `WebContentsView`.
 *
 * One instance lives in the main process. The renderer attaches it to the
 * rectangle it reserves for the editor, sends new bounds on resize, and detaches
 * it when the route unmounts. The view is sandboxed, has its own preload and can
 * only reach the native project store through the `vizzy:bridge` messages and
 * the two project IPC channels validated here.
 *
 * Crash policy: a renderer crash marks the state, tells the shell and reloads
 * once with a small budget, so a broken project cannot kill the app.
 */
import crypto from "node:crypto";
import path from "node:path";
import { BrowserWindow, dialog, shell, type WebContents, WebContentsView } from "electron";
import type { VizzyBounds, VizzyOpenResult, VizzyProbe, VizzySaveResult, VizzyState } from "../shared/types";
import { logger } from "../services/logger";
import { VIZZY_INDEX_URL } from "./assets";
import { createVizzyBridge, type VizzyBridge } from "./bridge";
import {
  atomicWriteText,
  ensureProjectsDir,
  isInsidePath,
  parseProjectText,
  readProjectFile,
  serialiseProjectFile,
  projectFilePath,
} from "./project-store";

const CRASH_RELOAD_WINDOW_MS = 60_000;
const CRASH_RELOAD_BUDGET = 3;
const ACK_TIMEOUT_MS = 8_000;
/** `camxora-vizzy://vizzy` — the only origin the editor may navigate to. */
const VIZZY_ORIGIN = new URL(VIZZY_INDEX_URL).origin;

export interface VizzyHostDeps {
  /** The shell window the view is attached to. */
  getWindow: () => BrowserWindow | null;
  /** `dist-electron/vizzy-preload.cjs`. */
  preloadPath: string;
  /** `vizzy-dist/`. */
  root: string;
  /** Managed `projects/` directory. */
  projectsDir: string;
  /** Shell strip updates. */
  onState: (state: VizzyState) => void;
}

interface PendingAck {
  resolve: (result: { ok: boolean; error?: string }) => void;
  timer: NodeJS.Timeout;
}

function clampBounds(bounds: VizzyBounds, window: BrowserWindow | null): VizzyBounds {
  const content = window?.getContentBounds();
  const maxWidth = Math.max(0, content?.width ?? 0);
  const maxHeight = Math.max(0, content?.height ?? 0);
  const x = Math.max(0, Math.round(bounds.x));
  const y = Math.max(0, Math.round(bounds.y));
  const width = Math.max(1, Math.min(Math.round(bounds.width), maxWidth - x));
  const height = Math.max(1, Math.min(Math.round(bounds.height), maxHeight - y));
  return { x, y, width: Math.max(1, width), height: Math.max(1, height) };
}

export class VizzyHost {
  private view: WebContentsView | null = null;
  private bridge: VizzyBridge | null = null;
  private pendingAcks = new Map<string, PendingAck>();
  private crashTimes: number[] = [];
  private lastPath: string | null = null;
  private lastBounds: VizzyBounds | null = null;
  private attached = false;
  private state: VizzyState = {
    attached: false,
    ready: false,
    crashed: false,
    projectName: "",
    dirty: false,
    nodeCount: 0,
    fftTier: "unknown",
    crossOriginIsolated: false,
    path: null,
    error: null,
  };

  constructor(private readonly deps: VizzyHostDeps) {}

  getState(): VizzyState {
    return { ...this.state };
  }

  /** True only for the hosted editor's webContents (channel guard). */
  isViewSender(sender: WebContents): boolean {
    const contents = this.view?.webContents;
    return Boolean(contents && !contents.isDestroyed() && contents.id === sender.id);
  }

  /** True only for the shell window's webContents (channel guard). */
  isShellSender(sender: WebContents): boolean {
    const contents = this.deps.getWindow()?.webContents;
    return Boolean(contents && !contents.isDestroyed() && contents.id === sender.id);
  }

  /** Route a `vizzy:bridge` message from the hosted view. */
  async handleViewMessage(message: unknown): Promise<void> {
    await this.bridge?.handleViewMessage(message);
  }

  hasView(): boolean {
    return Boolean(this.view && !this.view.webContents.isDestroyed());
  }

  /**
   * Create or re-place the view. The first call creates the `WebContentsView`,
   * attaches it to the window content view and loads the editor.
   */
  attach(bounds: VizzyBounds): VizzyState {
    const window = this.deps.getWindow();
    if (!window) {
      this.update({ attached: false, error: "The Camxora window is not available." });
      return this.getState();
    }

    if (!this.view || this.view.webContents.isDestroyed()) {
      this.createView();
    }

    const clamped = clampBounds(bounds, window);
    this.lastBounds = clamped;
    this.view!.setBounds(clamped);
    if (!this.attached) {
      window.contentView.addChildView(this.view!);
      this.attached = true;
    }
    this.update({ attached: true, error: null });
    return this.getState();
  }

  setBounds(bounds: VizzyBounds): void {
    if (!this.view || !this.attached) return;
    const clamped = clampBounds(bounds, this.deps.getWindow());
    this.lastBounds = clamped;
    this.view.setBounds(clamped);
  }

  /**
   * Remove the view from the window and stop the editor. Called on route leave
   * and on window close, so no editor process survives the page.
   */
  detach(): void {
    this.destroyView();
    this.update({ attached: false, ready: false });
  }

  /** Reload the editor; used by the crash notice and the shell strip. */
  reload(): void {
    const contents = this.view?.webContents;
    if (!contents || contents.isDestroyed()) {
      const window = this.deps.getWindow();
      if (!window) return;
      this.createView();
      const view = this.view;
      if (view) {
        view.setBounds(clampBounds(this.lastBounds ?? { x: 0, y: 0, width: 1, height: 1 }, window));
        if (!this.attached) {
          window.contentView.addChildView(view);
          this.attached = true;
        }
      }
      this.update({ attached: true, crashed: false, error: null, ready: false });
      return;
    }
    this.update({ crashed: false, error: null, ready: false });
    contents.reload();
  }

  /** Live diagnostics for the shell and the E2E harness. */
  async probe(timeoutMs = 5_000): Promise<VizzyProbe | null> {
    const contents = this.view?.webContents;
    if (!contents || contents.isDestroyed()) return null;
    const script = `(() => {
      const test = window.__vizzyTest;
      let webgl2 = false;
      try {
        const canvas = document.createElement("canvas");
        webgl2 = Boolean(canvas.getContext("webgl2"));
      } catch {
        webgl2 = false;
      }
      if (!test) {
        return { ready: false, projectName: "", dirty: false, nodeCount: 0,
          crossOriginIsolated: false, fftTier: "unknown", webgl2 };
      }
      return {
        ready: test.ready === true,
        projectName: String(test.projectName ?? ""),
        dirty: test.dirty === true,
        nodeCount: Number(test.nodeCount ?? 0),
        crossOriginIsolated: test.crossOriginIsolated === true,
        fftTier: String(test.fftTier ?? "unknown"),
        webgl2,
      };
    })()`;
    const value: unknown = await Promise.race([
      contents.executeJavaScript(script, true),
      new Promise((resolve) => setTimeout(() => resolve(null), timeoutMs)),
    ]);
    if (!value || typeof value !== "object") return null;
    const probe = value as Omit<VizzyProbe, "url">;
    const state = this.update({
      ready: probe.ready === true,
      projectName: probe.projectName,
      dirty: probe.dirty,
      nodeCount: probe.nodeCount,
      crossOriginIsolated: probe.crossOriginIsolated,
      fftTier: probe.fftTier,
    });
    let url = VIZZY_INDEX_URL;
    try {
      url = contents.getURL() || VIZZY_INDEX_URL;
    } catch {
      /* the renderer died between the probe and the read */
    }
    return { url, ...probe, ready: state.ready };
  }

  /** Current project snapshot as the editor serialises it. */
  async readProjectJson(): Promise<string> {
    const contents = this.view?.webContents;
    if (!contents || contents.isDestroyed()) {
      throw new Error("The Vizzy editor is not attached.");
    }
    const value: unknown = await contents.executeJavaScript(
      "window.__vizzyTest ? window.__vizzyTest.readProjectJson() : null",
      true,
    );
    if (typeof value !== "string" || value.length === 0) {
      throw new Error("The Vizzy editor is not ready to save yet.");
    }
    return value;
  }

  /** Write a snapshot to `projects/` atomically. Shared by shell and view saves. */
  saveProject(name: string, json: string): VizzySaveResult {
    const parsed = parseProjectText(json);
    if (!parsed.ok) throw new Error(parsed.message);
    const projectName =
      typeof parsed.snapshot.project === "object" && parsed.snapshot.project !== null
        ? String((parsed.snapshot.project as Record<string, unknown>).name ?? name)
        : name;
    const directory = ensureProjectsDir(this.deps.projectsDir);
    const filePath = projectFilePath(directory, projectName);
    const contents = serialiseProjectFile(parsed.snapshot);
    atomicWriteText(filePath, contents);

    const bytes = Buffer.byteLength(contents, "utf8");
    this.lastPath = filePath;
    this.update({ projectName, path: filePath, dirty: false, error: null });
    logger.info("vizzy project saved", { file: path.basename(filePath), bytes });
    this.notifySaved(filePath);
    return { path: filePath, name: projectName, bytes };
  }

  /** Shell strip Save: read the live snapshot, then write it. */
  async saveCurrent(): Promise<VizzySaveResult> {
    const json = await this.readProjectJson();
    return this.saveProject(this.state.projectName || "untitled-project", json);
  }

  /** Native Open dialog, defaulting to the managed projects directory. */
  async openFromDialog(): Promise<VizzyOpenResult | null> {
    if (!this.hasView()) throw new Error("Open the Vizzy editor first.");
    const directory = ensureProjectsDir(this.deps.projectsDir);
    const window = this.deps.getWindow();
    const options = {
      title: "Open Vizzy project",
      defaultPath: directory,
      properties: ["openFile"] as Array<"openFile">,
      filters: [
        { name: "Vizzy project", extensions: ["json"] },
        { name: "All files", extensions: ["*"] },
      ],
    };
    const result = window
      ? await dialog.showOpenDialog(window, options)
      : await dialog.showOpenDialog(options);
    if (result.canceled || result.filePaths.length === 0) return null;
    return this.openPath(result.filePaths[0]);
  }

  /**
   * Open a specific file. Paths outside the managed projects directory are only
   * accepted in E2E builds so the harness can open a fixture.
   */
  async openPath(filePath: string): Promise<VizzyOpenResult> {
    if (!this.hasView() || !this.bridge) throw new Error("Open the Vizzy editor first.");
    const resolved = path.resolve(filePath);
    const insideProjects = isInsidePath(this.deps.projectsDir, resolved);
    if (!insideProjects && process.env.CAMXORA_E2E !== "1") {
      throw new Error("Only projects inside the Camxora projects folder can be opened.");
    }

    const read = readProjectFile(resolved);
    if (!read.ok) throw new Error(read.message);
    const project = read.snapshot.project as Record<string, unknown>;
    const name = typeof project.name === "string" ? project.name : path.basename(resolved);

    const requestId = crypto.randomUUID();
    const ack = this.waitForAck(requestId);
    this.bridge.send({
      v: 1,
      type: "vizzy:open-project-json",
      requestId,
      path: resolved,
      name,
      json: read.text,
    });
    const result = await ack;
    if (!result.ok) throw new Error(result.error ?? "The editor could not open that project.");

    this.lastPath = resolved;
    const nodeCount = Array.isArray(read.snapshot.nodes) ? read.snapshot.nodes.length : 0;
    this.update({ projectName: name, dirty: false, nodeCount, path: resolved, error: null });
    return { path: resolved, name, nodeCount };
  }

  dispose(): void {
    for (const [, pending] of this.pendingAcks) {
      clearTimeout(pending.timer);
      pending.resolve({ ok: false, error: "The Vizzy view was closed." });
    }
    this.pendingAcks.clear();
    this.destroyView();
  }

  /* ---------------------------------------------------------------- */

  private createView(): void {
    const view = new WebContentsView({
      webPreferences: {
        preload: this.deps.preloadPath,
        contextIsolation: true,
        sandbox: true,
        nodeIntegration: false,
        webSecurity: true,
        spellcheck: false,
        backgroundThrottling: false,
      },
    });
    view.setBackgroundColor("#070a13");
    this.view = view;
    this.attached = false;

    const contents = view.webContents;

    contents.setWindowOpenHandler(({ url }) => {
      if (/^https?:\/\//i.test(url)) void shell.openExternal(url);
      return { action: "deny" };
    });

    contents.on("will-navigate", (event, url) => {
      // The editor never navigates away from its own host origin.
      if (url !== VIZZY_INDEX_URL && !url.startsWith(`${VIZZY_ORIGIN}/`)) {
        event.preventDefault();
        if (/^https?:\/\//i.test(url)) void shell.openExternal(url);
      }
    });

    contents.on("render-process-gone", (_event, details) => {
      logger.error("vizzy render process gone", { reason: details.reason });
      this.clearViewState();
      this.update({
        crashed: true,
        ready: false,
        error: `The Vizzy editor stopped responding (${details.reason}).`,
      });
      this.scheduleCrashReload(details.reason === "clean-exit");
    });

    contents.on("did-fail-load", (_event, code, description, url) => {
      if (code === -3) return; // aborted navigation, e.g. a reload
      logger.error("vizzy load failed", { code, description, url });
      this.update({ ready: false, error: `The Vizzy editor failed to load (${description}).` });
    });

    contents.on("console-message", (_event, level, message, line, sourceId) => {
      if (level >= 2) logger.warn("vizzy console", { message, line, sourceId });
    });

    this.bridge = createVizzyBridge({
      contents,
      handlers: {
        saveProject: async (input) => {
          const result = this.saveProject(input.name, await this.decodeBytes(input.bytes));
          return { path: result.path };
        },
        openProject: async () => {
          const opened = await this.openFromDialog();
          return opened ? { name: opened.name, bytes: new ArrayBuffer(0) } : null;
        },
        pickMedia: async () => null,
        startExport: async () => {
          throw new Error("Native export lands in the pipeline milestone.");
        },
        cancelExport: async () => false,
        appInfo: async () => ({ version: "2.0.0", env: process.env.NODE_ENV ?? "production" }),
        log: (level, message, detail) => {
          const write = level === "warn" ? logger.warn : level === "error" ? logger.error : logger.info;
          write("vizzy view", { message, detail });
        },
      },
      onDirty: (dirty) => this.update({ dirty }),
      onState: (state) => this.update(state),
      onAck: (payload) => this.resolveAck(payload),
    });

    void contents.loadURL(VIZZY_INDEX_URL).catch((error: unknown) => {
      logger.error("vizzy load error", { error: String(error) });
      this.update({ ready: false, error: "The Vizzy editor could not be loaded." });
    });
  }

  /** Bridge `vizzy:save` carries an ArrayBuffer; accept only text JSON. */
  private async decodeBytes(bytes: ArrayBuffer): Promise<string> {
    return Buffer.from(bytes).toString("utf8");
  }

  private destroyView(): void {
    const view = this.view;
    this.view = null;
    this.bridge?.dispose();
    this.bridge = null;
    this.clearViewState();
    if (!view) return;
    const window = this.deps.getWindow();
    if (this.attached) {
      try {
        window?.contentView.removeChildView(view);
      } catch {
        /* the window may already be gone */
      }
    }
    this.attached = false;
    if (!view.webContents.isDestroyed()) view.webContents.close();
  }

  private clearViewState(): void {
    this.state = {
      ...this.state,
      ready: false,
      crossOriginIsolated: false,
    };
  }

  private scheduleCrashReload(cleanExit: boolean): void {
    if (cleanExit) return;
    const now = Date.now();
    this.crashTimes = this.crashTimes.filter((time) => now - time < CRASH_RELOAD_WINDOW_MS);
    if (this.crashTimes.length >= CRASH_RELOAD_BUDGET) {
      logger.error("vizzy crash loop detected; not reloading");
      return;
    }
    this.crashTimes.push(now);
    setTimeout(() => {
      if (this.state.crashed) this.reload();
    }, 1_000);
  }

  private waitForAck(requestId: string): Promise<{ ok: boolean; error?: string }> {
    return new Promise((resolve) => {
      const timer = setTimeout(() => {
        this.pendingAcks.delete(requestId);
        resolve({ ok: false, error: "The editor did not confirm the project." });
      }, ACK_TIMEOUT_MS);
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

  private notifySaved(filePath: string): void {
    this.bridge?.send({ v: 1, type: "vizzy:project-saved", path: filePath });
  }

  private update(patch: Partial<VizzyState>): VizzyState {
    this.state = { ...this.state, ...patch, path: this.lastPath ?? this.state.path };
    this.deps.onState(this.getState());
    return this.state;
  }
}
