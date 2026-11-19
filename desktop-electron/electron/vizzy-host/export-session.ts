/**
 * One in-flight Vizzy export, shared by every editor surface.
 *
 * The hosted `WebContentsView` and the hidden batch render window both run the
 * editor's own exporter. The only difference is which `webContents` the chunks
 * arrive from and how the surface reports "ready". Everything else — settings
 * resolution, the destination file inside `renders/`, progress, cancellation,
 * cleanup and the ffprobe validation — lives here so the two paths cannot
 * drift apart.
 *
 * Files are the only durable artefact: the host owns the handle, the editor
 * never learns a path it can write to.
 */
import crypto from "node:crypto";
import fs from "node:fs";
import type { WebContents } from "electron";
import type { VizzyExportOutcome, VizzyExportProgress, VizzyExportResult } from "../shared/types";
import { probe } from "../services/ffmpeg";
import { logger } from "../services/logger";
import type { VizzyBridge } from "./bridge";
import {
  RenderChunkWriter,
  deleteRenderFile,
  ensureRendersDir,
  renderFileNameForTemplate,
  resolveExportSettings,
  uniqueRenderPath,
  type ResolvedVizzyExportSettings,
  type VizzyExportSettingsInput,
  type VizzyProjectInfo,
} from "./renders";

/** How long the editor gets to abort after a cancel before the host cleans up. */
const EXPORT_CANCEL_GRACE_MS = 5_000;
/** The editor must report its first frame within this window. */
const EXPORT_START_TIMEOUT_MS = 60_000;
/** Hard ceiling for one export; a stuck encoder must not hold the file open. */
const EXPORT_TIMEOUT_MS = 60 * 60_000;

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

export interface VizzyExportSessionDeps {
  /** Managed `renders/` directory; the only place an export may write. */
  rendersDir: string;
  getContents: () => WebContents | null;
  getBridge: () => VizzyBridge | null;
  /** The surface's editor is loaded and idle enough to export. */
  isReady: () => boolean;
  /** Fallback output stem when the caller does not name one. */
  defaultName: () => string;
  /** Project defaults for the export popover / a named render. */
  getProjectInfo: () => Promise<VizzyProjectInfo | null>;
  onProgress?: (progress: VizzyExportProgress) => void;
}

export interface StartExportOptions {
  outputName?: string;
  /** Called as soon as the job id exists, so a cancel can address it. */
  onStarted?: (jobId: string) => void;
}

function totalFramesFor(settings: ResolvedVizzyExportSettings): number {
  return Math.max(1, Math.round(settings.duration * settings.fps));
}

export class VizzyExportSession {
  private job: ExportJob | null = null;

  constructor(private readonly deps: VizzyExportSessionDeps) {}

  get currentJobId(): string | null {
    return this.job?.id ?? null;
  }

  hasJob(): boolean {
    return Boolean(this.job);
  }

  /**
   * Render the live editor project to `renders/<slug>-<timestamp>.<ext>`.
   * Resolves when the job settles (done / cancelled / failed).
   */
  async start(
    input: VizzyExportSettingsInput | null,
    options: StartExportOptions = {},
  ): Promise<VizzyExportOutcome> {
    const bridge = this.deps.getBridge();
    const contents = this.deps.getContents();
    if (!contents || contents.isDestroyed() || !bridge) {
      throw new Error("Open the Vizzy editor first.");
    }
    if (!this.deps.isReady()) throw new Error("The Vizzy editor is still starting.");
    if (this.job) throw new Error("An export is already running.");

    const project = await this.deps.getProjectInfo();
    const settings = resolveExportSettings(input, project);
    const directory = ensureRendersDir(this.deps.rendersDir);
    const requestedName = options.outputName?.trim();
    const fileName = renderFileNameForTemplate(
      requestedName || project?.name || this.deps.defaultName() || "untitled-project",
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
    this.job = job;
    options.onStarted?.(job.id);
    job.startTimer = setTimeout(() => {
      void this.settleWithoutFile(job, {
        status: "failed",
        message: "The Vizzy editor did not start the export.",
      });
    }, EXPORT_START_TIMEOUT_MS);

    const total = totalFramesFor(settings);
    this.deps.onProgress?.({
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

    bridge.send({
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

  /** One encoder chunk written at its absolute file offset. */
  async writeChunk(input: {
    jobId: string;
    position: number;
    data: Uint8Array;
  }): Promise<{ bytes: number }> {
    const job = this.job;
    if (!job || job.id !== input.jobId) throw new Error("That export is no longer running.");
    if (job.cancelled) throw new Error("The export was cancelled.");
    const write = job.writeChain.then(() => job.writer.write(input.position, input.data));
    job.writeChain = write.catch(() => undefined);
    await write;
    return { bytes: job.writer.bytes };
  }

  /** Cancel: abort the editor's exporter, then delete the partial file. */
  cancel(jobId: string): boolean {
    const job = this.job;
    if (!job || job.id !== jobId) return false;
    if (job.cancelled) return true;
    job.cancelled = true;
    this.deps.getBridge()?.send({ v: 1, type: "vizzy:export-cancel", jobId: job.id });
    job.cancelTimer = setTimeout(() => {
      void this.settleWithoutFile(job, { status: "cancelled" });
    }, EXPORT_CANCEL_GRACE_MS);
    return true;
  }

  /** Cancel whatever this surface is running (used when it is closing). */
  cancelCurrent(): boolean {
    return this.job ? this.cancel(this.job.id) : false;
  }

  /** View progress → shell event. Unknown or cancelled jobs are ignored. */
  handleProgress(payload: { jobId: string; done: number; total: number; stage: string }): void {
    const job = this.job;
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
    this.deps.onProgress?.({
      jobId: job.id,
      done,
      total,
      percent: Math.round((done / total) * 100),
      stage: typeof payload.stage === "string" ? payload.stage.slice(0, 80) : "exporting",
    });
  }

  /** View completion signal; the host owns the final word on the file. */
  async handleFinished(payload: {
    jobId: string;
    ok: boolean;
    cancelled: boolean;
    frames: number;
    error?: string;
  }): Promise<void> {
    const job = this.job;
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

  /** The surface is going away: cancel and clean up, never leave a partial file. */
  abort(reason: string): void {
    const job = this.job;
    if (!job) return;
    logger.info("vizzy export aborted", { reason, file: job.fileName });
    job.cancelled = true;
    void this.settleWithoutFile(job, { status: "cancelled" });
  }

  private async settleDone(job: ExportJob): Promise<void> {
    if (job.settled) return;
    job.settled = true;
    this.clearTimers(job);
    if (this.job === job) this.job = null;

    let closeError: unknown = null;
    try {
      await job.writer.close();
    } catch (error) {
      closeError = error;
    }
    const bytes = job.writer.bytes;
    if (closeError || bytes <= 0) {
      this.removeFile(job);
      const message =
        closeError !== null
          ? `The render could not be closed: ${closeError instanceof Error ? closeError.message : String(closeError)}`
          : "The exporter wrote no video data.";
      logger.error("vizzy export failed", { file: job.fileName, error: message });
      this.deps.onProgress?.({
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
    this.deps.onProgress?.({
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
    this.clearTimers(job);
    if (this.job === job) this.job = null;
    try {
      await job.writer.close();
    } catch {
      /* the handle may already be closed */
    }
    this.removeFile(job);
    job.resolve(outcome);
  }

  private removeFile(job: ExportJob): void {
    const removed = deleteRenderFile(this.deps.rendersDir, job.fileName);
    if (removed) logger.info("vizzy export cleanup", { file: job.fileName });
  }

  private clearTimers(job: ExportJob): void {
    if (job.cancelTimer) clearTimeout(job.cancelTimer);
    if (job.startTimer) clearTimeout(job.startTimer);
    if (job.timeoutTimer) clearTimeout(job.timeoutTimer);
    job.cancelTimer = null;
    job.startTimer = null;
    job.timeoutTimer = null;
  }
}
