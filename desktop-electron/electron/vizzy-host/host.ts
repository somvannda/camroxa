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
import fs from "node:fs";
import path from "node:path";
import { BrowserWindow, dialog, shell, type WebContents, WebContentsView } from "electron";
import type {
  VizzyBounds,
  VizzyExportOutcome,
  VizzyExportProgress,
  VizzyExportResult,
  VizzyExportSettingsInput,
  VizzyOpenResult,
  VizzyProbe,
  VizzyRenderSummary,
  VizzySaveResult,
  VizzyState,
} from "../shared/types";
import { probe } from "../services/ffmpeg";
import { logger } from "../services/logger";
import { allowPickedFile, createMediaUrl } from "../services/media";
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
import {
  RenderChunkWriter,
  deleteRenderFile,
  ensureRendersDir,
  listRenderFiles,
  managedRenderPath,
  renderFileNameForTemplate,
  resolveExportSettings,
  uniqueRenderPath,
  type ResolvedVizzyExportSettings,
  type VizzyProjectInfo,
} from "./renders";

const CRASH_RELOAD_WINDOW_MS = 60_000;
const CRASH_RELOAD_BUDGET = 3;
const ACK_TIMEOUT_MS = 8_000;
/** How long the editor gets to abort after a cancel before the host cleans up. */
const EXPORT_CANCEL_GRACE_MS = 5_000;
/** The editor must report its first frame within this window. */
const EXPORT_START_TIMEOUT_MS = 60_000;
/** Hard ceiling for one export; a stuck encoder must not hold the file open. */
const EXPORT_TIMEOUT_MS = 60 * 60_000;
/** Decoding and analysing a run track may take a little while on a long song. */
const AUDIO_LOAD_TIMEOUT_MS = 180_000;
/** How long a re-shown view gets to paint before `capturePage()`. */
const THUMBNAIL_PAINT_TIMEOUT_MS = 2_000;
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
  /** Managed `renders/` directory; the only place an export may write. */
  rendersDir: string;
  /** Shell strip updates. */
  onState: (state: VizzyState) => void;
  /** Export progress, forwarded to the shell as `vizzy:export:progress`. */
  onExportProgress?: (progress: VizzyExportProgress) => void;
}

interface PendingAck {
  resolve: (result: { ok: boolean; error?: string }) => void;
  timer: NodeJS.Timeout;
}

/** One in-flight export. Only one job per host, and only inside `renders/`. */
interface ExportJob {
  id: string;
  settings: ResolvedVizzyExportSettings;
  filePath: string;
  fileName: string;
  writer: RenderChunkWriter;
  frames: number;
  startedAt: number;
  cancelled: boolean;
  settled: boolean;
  writeChain: Promise<void>;
  resolve: (outcome: VizzyExportOutcome) => void;
  promise: Promise<VizzyExportOutcome>;
  cancelTimer: NodeJS.Timeout | null;
  startTimer: NodeJS.Timeout | null;
  timeoutTimer: NodeJS.Timeout | null;
}

function totalFramesFor(settings: ResolvedVizzyExportSettings): number {
  return Math.max(1, Math.round(settings.duration * settings.fps));
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
  /** Shell modals hide the native view, which always paints above DOM. */
  private viewVisible = true;
  private exportJob: ExportJob | null = null;
  private state: VizzyState = {
    attached: false,
    ready: false,
    crashed: false,
    projectName: "",
    dirty: false,
    nodeCount: 0,
    projectWidth: 0,
    projectHeight: 0,
    projectFps: 0,
    projectDuration: 0,
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
    this.view!.setVisible(this.viewVisible);
    this.update({ attached: true, error: null });
    return this.getState();
  }

  /**
   * Show or hide the native editor view.
   *
   * A `WebContentsView` always paints above the shell DOM, so a shell dialog or
   * modal would be hidden behind it. Hiding the view keeps the editor process
   * (and its project) alive while the modal is open; the next shell layout
   * change re-applies the bounds and the visibility is restored explicitly.
   */
  setVisible(visible: boolean): void {
    this.viewVisible = visible;
    const view = this.view;
    if (!view || view.webContents.isDestroyed()) return;
    view.setVisible(visible);
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
    this.clearPendingAcks("The Vizzy view was closed.");
    this.abortExport("The Vizzy editor was closed.");
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
    const info = await this.readProjectInfo();
    const state = this.update({
      ready: probe.ready === true,
      projectName: probe.projectName,
      dirty: probe.dirty,
      nodeCount: probe.nodeCount,
      projectWidth: info?.width ?? this.state.projectWidth,
      projectHeight: info?.height ?? this.state.projectHeight,
      projectFps: info?.fps ?? this.state.projectFps,
      projectDuration: info?.duration ?? this.state.projectDuration,
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

  /** The live project as the editor serialises it, plus its parsed snapshot. */
  async readSnapshot(): Promise<{ json: string; snapshot: Record<string, unknown> }> {
    const json = await this.readProjectJson();
    const parsed = parseProjectText(json);
    if (!parsed.ok) throw new Error(parsed.message);
    return { json, snapshot: parsed.snapshot };
  }

  /**
   * Everything "Save as video template" needs from the live preview: the exact
   * snapshot JSON and a PNG capture of the editor.
   *
   * The shell hides the view while its modal is open, so re-show it briefly for
   * the capture. `capturePage()` on a hidden view would be blank on Windows.
   */
  async captureTemplateSource(): Promise<{
    json: string;
    snapshot: Record<string, unknown>;
    thumbnail: Uint8Array;
  }> {
    if (!this.hasView()) throw new Error("Open the Vizzy editor first.");
    if (!this.state.ready) throw new Error("The Vizzy editor is still starting.");
    const wasVisible = this.viewVisible;
    if (!wasVisible) {
      this.setVisible(true);
      await this.waitForPaint();
    }
    try {
      const { json, snapshot } = await this.readSnapshot();
      const contents = this.view?.webContents;
      if (!contents || contents.isDestroyed()) {
        throw new Error("The Vizzy editor is not attached.");
      }
      const image = await contents.capturePage();
      if (image.isEmpty()) {
        throw new Error("The editor preview could not be captured for the thumbnail.");
      }
      return { json, snapshot, thumbnail: new Uint8Array(image.toPNG()) };
    } finally {
      if (!wasVisible) this.setVisible(false);
    }
  }

  /**
   * Load a saved project (a video template, or any studio snapshot) into the
   * editor without going through a file on disk. This is the same command the
   * native Open path sends; the editor applies it with `applyProjectSnapshot`.
   */
  async openProjectJson(input: {
    json: string;
    name: string;
    path?: string | null;
  }): Promise<VizzyOpenResult> {
    if (!this.hasView() || !this.bridge) throw new Error("Open the Vizzy editor first.");
    const read = parseProjectText(input.json);
    if (!read.ok) throw new Error(read.message);
    const header = read.snapshot.project as Record<string, unknown>;
    const name =
      input.name.trim() || (typeof header.name === "string" ? header.name : "Video template");
    const resolved = input.path ? path.resolve(input.path) : null;
    const ack = await this.sendOpenProject({ json: read.text, name, path: resolved ?? "" });
    if (!ack.ok) throw new Error(ack.error ?? "The editor could not open that template.");
    this.lastPath = resolved;
    const nodeCount = Array.isArray(read.snapshot.nodes) ? read.snapshot.nodes.length : 0;
    const number = (value: unknown): number =>
      typeof value === "number" && Number.isFinite(value) ? value : 0;
    this.update({
      projectName: name,
      dirty: false,
      nodeCount,
      projectWidth: number(header.width),
      projectHeight: number(header.height),
      projectFps: number(header.fps),
      projectDuration: number(header.duration),
      path: resolved,
      error: null,
    });
    return { path: resolved ?? "", name, nodeCount };
  }

  /**
   * Load a run track into the editor. The file is streamed over
   * `camxora-media://` and decoded by the editor's own audio loader; the bytes
   * never enter the project file or a bridge payload.
   */
  async loadAudioTrack(filePath: string): Promise<{ name: string }> {
    if (!this.hasView() || !this.bridge) throw new Error("Open the Vizzy editor first.");
    if (!this.state.ready) throw new Error("The Vizzy editor is still starting.");
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
    const name = path.basename(resolved);
    const requestId = crypto.randomUUID();
    const ack = this.waitForAck(requestId, AUDIO_LOAD_TIMEOUT_MS);
    this.bridge.send({ v: 1, type: "vizzy:load-audio", requestId, name, url });
    const result = await ack;
    if (!result.ok) {
      throw new Error(result.error ?? "The editor could not load the run audio.");
    }
    return { name };
  }

  /** Open the editor's own Creations browser (all 91 staged templates). */
  async openCreationsBrowser(): Promise<boolean> {
    const contents = this.view?.webContents;
    if (!contents || contents.isDestroyed()) throw new Error("Open the Vizzy editor first.");
    const opened: unknown = await contents.executeJavaScript(
      "typeof window.editorOpenCreations === 'function' ? (window.editorOpenCreations(), true) : false",
      true,
    );
    if (opened !== true) throw new Error("The editor does not expose its Creations browser.");
    return true;
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

    const result = await this.sendOpenProject({ json: read.text, name, path: resolved });
    if (!result.ok) throw new Error(result.error ?? "The editor could not open that project.");

    this.lastPath = resolved;
    const nodeCount = Array.isArray(read.snapshot.nodes) ? read.snapshot.nodes.length : 0;
    const number = (value: unknown): number =>
      typeof value === "number" && Number.isFinite(value) ? value : 0;
    this.update({
      projectName: name,
      dirty: false,
      nodeCount,
      projectWidth: number(project.width),
      projectHeight: number(project.height),
      projectFps: number(project.fps),
      projectDuration: number(project.duration),
      path: resolved,
      error: null,
    });
    return { path: resolved, name, nodeCount };
  }

  /* ---------------------------------------------------------------- */
  /* Native export + managed renders                                   */
  /* ---------------------------------------------------------------- */

  /** Managed `renders/` files, newest first. */
  listRenders(): VizzyRenderSummary[] {
    return listRenderFiles(ensureRendersDir(this.deps.rendersDir));
  }

  /**
   * Render the live editor project to `renders/<slug>-<timestamp>.<ext>`.
   *
   * The editor's own exporter does the rendering; the host owns the file and
   * the settings. Resolves when the job settles (done / cancelled / failed).
   * `outputName` names the file from a template id instead of the project name.
   */
  async exportVideo(
    input: VizzyExportSettingsInput | null,
    options: { outputName?: string } = {},
  ): Promise<VizzyExportOutcome> {
    if (!this.hasView() || !this.bridge) throw new Error("Open the Vizzy editor first.");
    if (!this.state.ready) throw new Error("The Vizzy editor is still starting.");
    if (this.exportJob) throw new Error("An export is already running.");

    const project = await this.readProjectInfo();
    const settings = resolveExportSettings(input, project);
    const directory = ensureRendersDir(this.deps.rendersDir);
    const requestedName = options.outputName?.trim();
    const fileName = renderFileNameForTemplate(
      requestedName || project?.name || this.state.projectName || "untitled-project",
      settings.format,
    );
    const filePath = uniqueRenderPath(directory, fileName);
    const handle = await fs.promises.open(filePath, "w+");

    const writer = new RenderChunkWriter({
      writeAt: async (buffer, position) => {
        await handle.write(buffer, 0, buffer.byteLength, position);
      },
      close: async () => {
        try {
          await handle.sync();
        } finally {
          await handle.close();
        }
      },
    });

    let resolveJob: (outcome: VizzyExportOutcome) => void = () => undefined;
    const promise = new Promise<VizzyExportOutcome>((resolve) => {
      resolveJob = resolve;
    });
    const job: ExportJob = {
      id: crypto.randomUUID(),
      settings,
      filePath,
      fileName,
      writer,
      frames: 0,
      startedAt: Date.now(),
      cancelled: false,
      settled: false,
      writeChain: Promise.resolve(),
      resolve: resolveJob,
      promise,
      cancelTimer: null,
      startTimer: null,
      timeoutTimer: null,
    };
    this.exportJob = job;
    job.startTimer = setTimeout(() => {
      void this.settleWithoutFile(job, {
        status: "failed",
        message: "The Vizzy editor did not start the export.",
      });
    }, EXPORT_START_TIMEOUT_MS);

    const total = totalFramesFor(settings);
    this.deps.onExportProgress?.({
      jobId: job.id,
      done: 0,
      total,
      percent: 0,
      stage: "starting",
    });
    logger.info("vizzy export started", {
      file: fileName,
      width: settings.width,
      height: settings.height,
      fps: settings.fps,
      format: settings.format,
      codec: settings.codec,
      seconds: settings.duration,
    });

    this.bridge.send({
      v: 1,
      type: "vizzy:export-run",
      jobId: job.id,
      settings: {
        width: settings.width,
        height: settings.height,
        fps: settings.fps,
        format: settings.format,
        codec: settings.codec,
        bitrate: settings.bitrate,
        crf: settings.crf,
        start: settings.start,
        end: settings.end,
      },
    });

    return promise;
  }

  /** View-only: one encoder chunk written at its absolute file offset. */
  async writeExportChunk(input: {
    jobId: string;
    position: number;
    data: Uint8Array;
  }): Promise<{ bytes: number }> {
    const job = this.exportJob;
    if (!job || job.id !== input.jobId) throw new Error("That export is no longer running.");
    if (job.cancelled) throw new Error("The export was cancelled.");
    const write = job.writeChain.then(() => job.writer.write(input.position, input.data));
    job.writeChain = write.catch(() => undefined);
    await write;
    return { bytes: job.writer.bytes };
  }

  /** Shell cancel: abort the editor's exporter, then delete the partial file. */
  cancelExport(jobId: string): boolean {
    const job = this.exportJob;
    if (!job || job.id !== jobId) return false;
    if (job.cancelled) return true;
    job.cancelled = true;
    this.bridge?.send({ v: 1, type: "vizzy:export-cancel", jobId: job.id });
    job.cancelTimer = setTimeout(() => {
      void this.settleWithoutFile(job, { status: "cancelled" });
    }, EXPORT_CANCEL_GRACE_MS);
    return true;
  }

  /** View progress → shell event. Unknown or cancelled jobs are ignored. */
  handleExportProgress(payload: { jobId: string; done: number; total: number; stage: string }): void {
    const job = this.exportJob;
    if (!job || job.id !== payload.jobId || job.cancelled) return;
    if (job.startTimer) {
      // The exporter is alive; swap the start guard for the hard ceiling.
      clearTimeout(job.startTimer);
      job.startTimer = null;
      job.timeoutTimer = setTimeout(() => {
        void this.settleWithoutFile(job, {
          status: "failed",
          message: "The export timed out before it finished.",
        });
      }, EXPORT_TIMEOUT_MS);
    }
    const total = Math.max(1, Math.round(Number(payload.total) || totalFramesFor(job.settings)));
    const done = Math.min(total, Math.max(0, Math.round(Number(payload.done) || 0)));
    job.frames = Math.max(job.frames, done);
    this.deps.onExportProgress?.({
      jobId: job.id,
      done,
      total,
      percent: Math.round((done / total) * 100),
      stage: typeof payload.stage === "string" ? payload.stage.slice(0, 80) : "exporting",
    });
  }

  /** View completion signal; the host owns the final word on the file. */
  async handleExportFinished(payload: {
    jobId: string;
    ok: boolean;
    cancelled: boolean;
    frames: number;
    error?: string;
  }): Promise<void> {
    const job = this.exportJob;
    if (!job || job.id !== payload.jobId) return;
    if (Number.isFinite(payload.frames) && payload.frames > 0) {
      job.frames = Math.min(Math.round(payload.frames), totalFramesFor(job.settings));
    }
    if (job.cancelled || payload.cancelled) {
      await this.settleWithoutFile(job, { status: "cancelled" });
      return;
    }
    if (!payload.ok) {
      await this.settleWithoutFile(job, {
        status: "failed",
        message:
          typeof payload.error === "string" && payload.error.length > 0
            ? payload.error.slice(0, 400)
            : "The export failed before it wrote a file.",
      });
      return;
    }
    await this.settleDone(job);
  }

  /** Delete one managed render; anything outside `renders/` is refused. */
  deleteRender(name: string): boolean {
    const removed = deleteRenderFile(ensureRendersDir(this.deps.rendersDir), name);
    if (removed) logger.info("vizzy render deleted", { file: name });
    return removed;
  }

  /** Show a managed render in the OS file manager. */
  revealRender(name: string): boolean {
    const resolved = managedRenderPath(this.deps.rendersDir, name);
    if (!resolved || !fs.existsSync(resolved)) return false;
    shell.showItemInFolder(resolved);
    return true;
  }

  /** Opaque `camxora-media://` URL for inline playback of a managed render. */
  renderUrl(name: string): string | null {
    const resolved = managedRenderPath(this.deps.rendersDir, name);
    if (!resolved || !fs.existsSync(resolved)) return null;
    return createMediaUrl(resolved);
  }

  dispose(): void {
    this.clearPendingAcks("The Vizzy view was closed.");
    this.abortExport("The application is closing.");
    this.destroyView();
  }

  /* ---------------------------------------------------------------- */

  /** Send the editor an open command and wait for its acknowledgement. */
  private async sendOpenProject(input: {
    json: string;
    name: string;
    path: string;
  }): Promise<{ ok: boolean; error?: string }> {
    const bridge = this.bridge;
    if (!bridge) throw new Error("Open the Vizzy editor first.");
    const requestId = crypto.randomUUID();
    const ack = this.waitForAck(requestId);
    bridge.send({
      v: 1,
      type: "vizzy:open-project-json",
      requestId,
      path: input.path,
      name: input.name,
      json: input.json,
    });
    return ack;
  }

  /** Give a re-shown native view a couple of frames to paint. */
  private async waitForPaint(): Promise<void> {
    const contents = this.view?.webContents;
    if (!contents || contents.isDestroyed()) return;
    const script =
      "new Promise((resolve) => requestAnimationFrame(() => requestAnimationFrame(() => resolve(true))))";
    await Promise.race([
      contents.executeJavaScript(script, true),
      new Promise((resolve) => setTimeout(resolve, THUMBNAIL_PAINT_TIMEOUT_MS)),
    ]);
  }

  /** Project defaults for the export popover, read from the live editor. */
  private async readProjectInfo(): Promise<VizzyProjectInfo | null> {
    const contents = this.view?.webContents;
    if (!contents || contents.isDestroyed()) return null;
    const script = `(() => {
      const test = window.__vizzyTest;
      if (!test || typeof test.readProjectInfo !== "function") return null;
      try { return test.readProjectInfo(); } catch { return null; }
    })()`;
    const value: unknown = await Promise.race([
      contents.executeJavaScript(script, true),
      new Promise((resolve) => setTimeout(() => resolve(null), 3_000)),
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

  /** Cancel whatever is in flight because the view or the app is going away. */
  private abortExport(reason: string): void {
    const job = this.exportJob;
    if (!job) return;
    logger.info("vizzy export aborted", { reason, file: job.fileName });
    job.cancelled = true;
    void this.settleWithoutFile(job, { status: "cancelled" });
  }

  private async settleDone(job: ExportJob): Promise<void> {
    if (job.settled) return;
    job.settled = true;
    this.clearExportTimers(job);
    if (this.exportJob === job) this.exportJob = null;

    let closeError: unknown = null;
    try {
      await job.writer.close();
    } catch (error) {
      closeError = error;
    }
    const bytes = job.writer.bytes;
    if (closeError || bytes <= 0) {
      this.removeRenderFile(job);
      const message =
        closeError !== null
          ? `The render could not be closed: ${closeError instanceof Error ? closeError.message : String(closeError)}`
          : "The exporter wrote no video data.";
      logger.error("vizzy export failed", { file: job.fileName, error: message });
      this.deps.onExportProgress?.({
        jobId: job.id,
        done: 0,
        total: totalFramesFor(job.settings),
        percent: 0,
        stage: "failed",
      });
      job.resolve({ status: "failed", message });
      return;
    }

    let probed: Awaited<ReturnType<typeof probe>> | null = null;
    try {
      probed = await probe(job.filePath);
    } catch (error) {
      // ffprobe is optional at runtime; the file is still a real render.
      logger.warn("vizzy export probe failed", {
        file: job.fileName,
        error: String(error),
      });
    }

    const total = totalFramesFor(job.settings);
    const result: VizzyExportResult = {
      jobId: job.id,
      path: job.filePath,
      name: job.fileName,
      bytes,
      frames: job.frames || total,
      durationSec: probed?.durationSec || job.settings.duration,
      width: probed?.width ?? job.settings.width,
      height: probed?.height ?? job.settings.height,
      videoCodec: probed?.videoCodec ?? null,
      audioCodec: probed?.audioCodec ?? null,
      elapsedMs: Date.now() - job.startedAt,
    };
    logger.info("vizzy export finished", {
      file: job.fileName,
      bytes,
      frames: result.frames,
      ms: result.elapsedMs,
    });
    this.deps.onExportProgress?.({
      jobId: job.id,
      done: total,
      total,
      percent: 100,
      stage: "done",
    });
    job.resolve({ status: "done", result });
  }

  /** Close the handle, delete the partial file and settle the job. */
  private async settleWithoutFile(job: ExportJob, outcome: VizzyExportOutcome): Promise<void> {
    if (job.settled) return;
    job.settled = true;
    this.clearExportTimers(job);
    if (this.exportJob === job) this.exportJob = null;
    try {
      await job.writer.close();
    } catch {
      /* the handle may already be closed */
    }
    this.removeRenderFile(job);
    job.resolve(outcome);
  }

  private removeRenderFile(job: ExportJob): void {
    const removed = deleteRenderFile(this.deps.rendersDir, job.fileName);
    if (removed) logger.info("vizzy export cleanup", { file: job.fileName });
  }

  private clearExportTimers(job: ExportJob): void {
    if (job.cancelTimer) clearTimeout(job.cancelTimer);
    if (job.startTimer) clearTimeout(job.startTimer);
    if (job.timeoutTimer) clearTimeout(job.timeoutTimer);
    job.cancelTimer = null;
    job.startTimer = null;
    job.timeoutTimer = null;
  }

  private clearPendingAcks(reason: string): void {
    for (const [, pending] of this.pendingAcks) {
      clearTimeout(pending.timer);
      pending.resolve({ ok: false, error: reason });
    }
    this.pendingAcks.clear();
  }

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
    view.setVisible(this.viewVisible);
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
      this.abortExport("The Vizzy editor stopped responding.");
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
          // Exports are owned by the shell so progress, cancellation and the
          // output file have a single owner. The in-editor dialog keeps working
          // as a fallback and writes through the browser, not this bridge.
          throw new Error("Start exports from the Camxora Export action.");
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
      onExportProgress: (payload) => this.handleExportProgress(payload),
      onExportFinished: (payload) => void this.handleExportFinished(payload),
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
    this.viewVisible = true;
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

  private waitForAck(
    requestId: string,
    timeoutMs = ACK_TIMEOUT_MS,
  ): Promise<{ ok: boolean; error?: string }> {
    return new Promise((resolve) => {
      const timer = setTimeout(() => {
        this.pendingAcks.delete(requestId);
        resolve({ ok: false, error: "The editor did not confirm the project." });
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

  private notifySaved(filePath: string): void {
    this.bridge?.send({ v: 1, type: "vizzy:project-saved", path: filePath });
  }

  private update(patch: Partial<VizzyState>): VizzyState {
    this.state = {
      ...this.state,
      ...patch,
      path: patch.path !== undefined ? patch.path : (this.lastPath ?? this.state.path),
    };
    this.deps.onState(this.getState());
    return this.state;
  }
}
