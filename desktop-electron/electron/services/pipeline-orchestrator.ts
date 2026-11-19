/**
 * Video pipeline orchestration: template → render plan → audio → editor export
 * → ffprobe → optional merge.
 *
 * Everything Electron-specific is injected, so the whole flow runs in vitest
 * with a fake renderer. The render port is the offscreen Vizzy host in the app;
 * here it is only "render this plan and hand back a validated file".
 *
 * See `docs/electron-desktop/vizzy/BATCH-ORCHESTRATION.md`.
 */
import path from "node:path";
import fs from "node:fs";
import type { Store } from "./database";
import {
  runPipelineQueue,
  PipelineCancelledError,
  type PipelineRunSummary,
} from "./pipeline-batch";
import {
  cancelQueuedJobs,
  listQueue,
  updateQueueJob,
  type PipelineJobStatus,
  type PipelineQueueItem,
} from "./pipeline-queue";
import { buildPipelineRenderPlan, type PipelineRenderPlan } from "./pipeline-run";
import type { PipelineTemplate } from "./pipeline-templates";
import { uniqueOutputPath } from "./pipeline-sources";

export interface PipelineTemplateSource {
  id: string;
  name: string;
  projectJson: string;
  pipeline: PipelineTemplate;
}

export interface PipelineRenderInput {
  job: PipelineQueueItem;
  plan: PipelineRenderPlan;
  templateName: string;
  /** File stem; the render host turns it into `<slug>-<timestamp>.mp4`. */
  outputName: string;
  /** Export progress mapped to the queue stages. */
  onProgress?: (progress: { percent: number; stage: "rendering" | "encoding" }) => void;
  /** The port calls this with its cancel function while the render runs. */
  registerCancel?: (cancel: (() => void) | null) => void;
  /** Checked before the exporter starts; a cancelled job must not write a file. */
  isCancelled?: () => boolean;
}

export interface PipelineRenderResult {
  output: string;
  bytes?: number;
}

export interface PipelineMediaInfo {
  durationSec: number;
  width: number | null;
  height: number | null;
  videoCodec: string | null;
  audioCodec?: string | null;
}

export interface PipelineOrchestratorDeps {
  store: Store;
  readTemplate: (id: string) => PipelineTemplateSource;
  /** FFprobe duration of the run audio. */
  probeDuration: (filePath: string) => Promise<number>;
  /** FFprobe the rendered file; used to accept or reject the output. */
  probeMedia: (filePath: string) => Promise<PipelineMediaInfo>;
  render: (input: PipelineRenderInput) => Promise<PipelineRenderResult>;
  /** FFmpeg concat; `output` is the absolute merged path. */
  merge?: (inputs: string[], output: string) => Promise<{ output: string }>;
  /** `camxora-media://` URL for a run background/logo. */
  toMediaUrl?: (filePath: string) => string | null;
  onEvent?: (event: PipelineRunEvent) => void;
  now?: () => number;
  /** Queue progress is throttled to at most one write per interval. */
  progressIntervalMs?: number;
}

export interface PipelineRunEvent {
  batchId: string;
  reason: "started" | "progress" | "done" | "failed" | "cancelled" | "merging";
}

/** Which queue stage a raw exporter stage belongs to. */
export function queueStageFor(exportStage: string): "rendering" | "encoding" {
  const stage = exportStage.toLowerCase();
  if (/(encod|mux|join|writ)/.test(stage)) return "encoding";
  return "rendering";
}

/**
 * Render progress as a queue percentage. Rendering owns 0–85, encoding 85–99;
 * 100 is only written once the file is validated.
 */
export function queueProgressFor(done: number, total: number, exportStage: string): number {
  const safeTotal = Math.max(1, Math.round(total));
  const ratio = Math.max(0, Math.min(1, Math.round(done) / safeTotal));
  const stage = queueStageFor(exportStage);
  const percent = stage === "encoding" ? 85 + ratio * 14 : ratio * 85;
  return Math.max(0, Math.min(99, Math.round(percent)));
}

export interface ProgressThrottle {
  /** Returns the percent to write, or null when the write is too soon. */
  shouldWrite(percent: number, force?: boolean): boolean;
  lastPercent(): number;
}

export function createProgressThrottle(
  intervalMs: number,
  now: () => number = Date.now,
): ProgressThrottle {
  let lastAt = Number.NEGATIVE_INFINITY;
  let last = -1;
  return {
    shouldWrite(percent: number, force = false): boolean {
      const value = Math.max(0, Math.min(99, Math.round(percent)));
      const stamp = now();
      if (!force && stamp - lastAt < intervalMs) return false;
      if (value === last && !force) return false;
      lastAt = stamp;
      last = value;
      return true;
    },
    lastPercent() {
      return last;
    },
  };
}

function messageOf(error: unknown): string {
  return error instanceof Error ? error.message : String(error);
}

/** Best-effort delete for a render that must not survive a cancel. */
function removeQuietly(filePath: string | undefined): void {
  if (!filePath) return;
  try {
    if (fs.existsSync(filePath)) fs.rmSync(filePath, { force: true });
  } catch {
    // The file may be locked for a moment; the row is still cancelled.
  }
}

/** Batch status derived from its rows, so a reload never shows a stale state. */
export function deriveBatchStatus(
  jobs: Array<Pick<PipelineQueueItem, "status">>,
  merging: boolean,
): "idle" | "running" | "merging" | "done" | "failed" | "cancelled" {
  if (merging) return "merging";
  if (jobs.length === 0) return "idle";
  if (jobs.some((job) => job.status === "queued" || job.status === "rendering" || job.status === "encoding" || job.status === "merging")) {
    return "running";
  }
  if (jobs.some((job) => job.status === "failed")) return "failed";
  if (jobs.every((job) => job.status === "cancelled")) return "cancelled";
  return "done";
}

export class PipelineRunner {
  private running = false;
  private cancelled = false;
  private cancelRender: (() => void) | null = null;
  private readonly now: () => number;

  constructor(private readonly deps: PipelineOrchestratorDeps) {
    this.now = deps.now ?? Date.now;
  }

  isRunning(): boolean {
    return this.running;
  }

  /**
   * Stop the current render and cancel queued rows. Safe to call when idle.
   * Returns the batch ids that were in flight.
   */
  cancel(): { cancelled: boolean; batchIds: string[] } {
    if (!this.running) {
      const queued = cancelQueuedJobs(this.deps.store);
      return { cancelled: queued > 0, batchIds: [] };
    }
    this.cancelled = true;
    const batchIds = [
      ...new Set(
        listQueue(this.deps.store)
          .filter((job) => job.status === "queued")
          .map((job) => job.batchId),
      ),
    ];
    cancelQueuedJobs(this.deps.store);
    try {
      this.cancelRender?.();
    } catch {
      // Cancelling an already-settled job is not an error.
    }
    for (const batchId of batchIds) this.deps.onEvent?.({ batchId, reason: "cancelled" });
    return { cancelled: true, batchIds };
  }

  /** Retry is deliberately explicit: failed/cancelled rows are re-enqueued by the caller. */
  async run(): Promise<PipelineRunSummary> {
    if (this.running) throw new Error("The video pipeline is already running.");
    this.running = true;
    this.cancelled = false;
    const store = this.deps.store;
    const startedBatches = [
      ...new Set(
        listQueue(store)
          .filter((job) => job.status === "queued")
          .map((job) => job.batchId),
      ),
    ];
    for (const batchId of startedBatches) {
      const batch = store.getBatch(batchId);
      if (!batch) continue;
      store.upsertBatch({ ...batch, status: "running", error: null, updatedAt: this.now() });
      this.deps.onEvent?.({ batchId, reason: "started" });
    }

    try {
      return await runPipelineQueue({
        store,
        shouldStop: () => this.cancelled,
        shouldMerge: (batchId) => store.getBatch(batchId)?.merge === true,
        onUpdate: (job) => this.deps.onEvent?.({ batchId: job.batchId, reason: "progress" }),
        render: (job) => this.renderOne(job),
        merge: this.deps.merge
          ? (outputs, batchId) => this.mergeBatch(outputs, batchId)
          : undefined,
      });
    } finally {
      this.running = false;
      this.cancelRender = null;
      this.finaliseBatches(startedBatches);
    }
  }

  private finaliseBatches(batchIds: string[]): void {
    const store = this.deps.store;
    for (const batchId of batchIds) {
      const batch = store.getBatch(batchId);
      if (!batch) continue;
      const jobs = listQueue(store).filter((job) => job.batchId === batchId);
      const status = batch.error && jobs.every((job) => job.status !== "queued")
        ? "failed"
        : deriveBatchStatus(jobs, false);
      store.upsertBatch({ ...batch, status, updatedAt: this.now() });
      this.deps.onEvent?.({
        batchId,
        reason: status === "failed" ? "failed" : status === "cancelled" ? "cancelled" : "done",
      });
    }
  }

  private async renderOne(job: PipelineQueueItem): Promise<{ output: string }> {
    if (this.cancelled) throw new PipelineCancelledError();
    const store = this.deps.store;
    const template = this.deps.readTemplate(job.templateId);
    const audioDurationSec = await this.deps.probeDuration(job.audioPath);
    if (this.cancelled) throw new PipelineCancelledError();
    if (!Number.isFinite(audioDurationSec) || audioDurationSec <= 0) {
      throw new Error("The run audio has no usable duration.");
    }

    const inputs: Parameters<typeof buildPipelineRenderPlan>[1]["inputs"] = {
      title: job.title || undefined,
      artist: job.artist || undefined,
      album: job.album || undefined,
    };
    if (job.backgroundPath && this.deps.toMediaUrl) {
      const url = this.deps.toMediaUrl(job.backgroundPath);
      if (url) inputs.backgroundUrl = url;
    }
    if (job.logoPath && this.deps.toMediaUrl) {
      const url = this.deps.toMediaUrl(job.logoPath);
      if (url) inputs.logoUrl = url;
    }

    const plan = buildPipelineRenderPlan(
      { id: template.id, projectJson: template.projectJson, pipeline: template.pipeline },
      { audioDurationSec, inputs, expectedKind: job.branch },
    );

    const throttle = createProgressThrottle(this.deps.progressIntervalMs ?? 500, this.now);
    const writeProgress = (percent: number, stage: PipelineJobStatus, force = false) => {
      if (!throttle.shouldWrite(percent, force)) return;
      updateQueueJob(store, job.id, { status: stage, stage, progress: percent });
      this.deps.onEvent?.({ batchId: job.batchId, reason: "progress" });
    };

    updateQueueJob(store, job.id, { status: "rendering", stage: "rendering", progress: 0 });
    this.deps.onEvent?.({ batchId: job.batchId, reason: "progress" });

    const result = await this.deps.render({
      job,
      plan,
      templateName: template.name,
      outputName: job.title || path.basename(job.audioPath, path.extname(job.audioPath)),
      onProgress: (progress) => {
        writeProgress(progress.percent, progress.stage);
      },
      registerCancel: (cancel) => {
        this.cancelRender = cancel;
        if (this.cancelled) cancel?.();
      },
      isCancelled: () => this.cancelled,
    });

    if (this.cancelled) {
      // A cancel that lands after the exporter settled still leaves no file.
      removeQuietly(result.output);
      throw new PipelineCancelledError();
    }

    const media = await this.deps.probeMedia(result.output);
    if (!media.width || !media.height || !media.durationSec) {
      throw new Error(
        `The render is not a valid video (${media.videoCodec ?? "no video stream"}).`,
      );
    }
    this.cancelRender = null;
    updateQueueJob(store, job.id, {
      status: "done",
      stage: "done",
      progress: 100,
      error: null,
      output: result.output,
    });
    this.deps.onEvent?.({ batchId: job.batchId, reason: "progress" });
    return { output: result.output };
  }

  private async mergeBatch(
    outputs: string[],
    batchId: string,
  ): Promise<{ output: string }> {
    const store = this.deps.store;
    const batch = store.getBatch(batchId);
    if (!batch?.merge || !this.deps.merge) return { output: "" };
    store.upsertBatch({ ...batch, status: "merging", error: null, updatedAt: this.now() });
    this.deps.onEvent?.({ batchId, reason: "merging" });

    const output =
      batch.mergedOutput ??
      uniqueOutputPath(batch.outputDir, `${batchId}-merged`);
    try {
      const merged = await this.deps.merge(outputs, output);
      const media = await this.deps.probeMedia(merged.output);
      if (!media.width || !media.height || !media.durationSec) {
        throw new Error("The merged file is not a valid video.");
      }
      store.upsertBatch({
        ...batch,
        status: "done",
        error: null,
        mergedOutput: merged.output,
        updatedAt: this.now(),
      });
      this.deps.onEvent?.({ batchId, reason: "done" });
      return { output: merged.output };
    } catch (error) {
      store.upsertBatch({
        ...batch,
        status: "failed",
        error: `Merge failed: ${messageOf(error)}`,
        updatedAt: this.now(),
      });
      this.deps.onEvent?.({ batchId, reason: "failed" });
      return { output: "" };
    }
  }
}
