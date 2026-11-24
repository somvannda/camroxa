/**
 * IPC surface for the video pipeline (P7 batch orchestration).
 *
 * The shell renders the durable queue, so every handler here is thin: read the
 * queue, enqueue work, start/cancel/retry, reveal an output. Rendering itself
 * happens in the offscreen Vizzy host; merging uses the existing FFmpeg concat
 * plan. Nothing here uploads.
 */
import fs from "node:fs";
import path from "node:path";
import { app, BrowserWindow, ipcMain, shell } from "electron";
import { z } from "zod";
import { probe } from "../services/ffmpeg";
import { logger } from "../services/logger";
import { allowPickedFile, createMediaUrl } from "../services/media";
import { getAppPaths } from "../services/paths";
import { AutoVideoCoordinator } from "../services/auto-video-coordinator";
import {
  PipelineCancelledError,
} from "../services/pipeline-batch";
import { mergeVideos, planConcat } from "../services/pipeline-merge";
import {
  PipelineRunner,
  queueProgressFor,
  queueStageFor,
} from "../services/pipeline-orchestrator";
import {
  clearFinishedJobs,
  enqueuePipelineJobs,
  jobsForBatch,
  listQueue,
  updateQueueJob,
  reconcileInterruptedJobs,
  retryableJobs,
} from "../services/pipeline-queue";
import { uniqueOutputPath } from "../services/pipeline-sources";
import { enqueuePipelineRequest } from "../services/pipeline-enqueue";
import type { Store } from "../services/database";
import { getStore } from "../services/store";
import { readVideoTemplate } from "../services/video-templates";
import {
  fail,
  ok,
  type PipelineAutoStatus,
  type PipelineBatchInfo,
  type PipelineEnqueueResult,
  type PipelineJobInfo,
  type PipelineSnapshot,
} from "../shared/types";
import { toError } from "./errors";
import type { VizzyHost } from "../vizzy-host/host";

const branchSchema = z.enum(["long", "reel"]);

const enqueueSchema = z
  .object({
    batchId: z.string().min(1).max(120).optional(),
    outputDir: z.string().min(1).max(4096),
    merge: z.boolean().optional(),
    mergeName: z.string().max(200).optional(),
    autostart: z.boolean().optional(),
    jobs: z
      .array(
        z
          .object({
            branch: branchSchema,
            templateId: z.string().min(1).max(200),
            audioPath: z.string().max(4096).optional(),
            audioDir: z.string().max(4096).optional(),
            audioBranch: z.enum(["ok", "alt"]).optional(),
            title: z.string().max(300).optional(),
            artist: z.string().max(300).optional(),
            album: z.string().max(300).optional(),
            backgroundPath: z.string().max(4096).optional(),
            logoPath: z.string().max(4096).optional(),
          })
          .strict(),
      )
      .min(1)
      .max(200),
  })
  .strict();

const retrySchema = z.object({ batchId: z.string().min(1).max(120).optional() }).strict();
const forceSchema = z
  .object({
    mode: z.enum(["force", "repair", "single"]),
    batchId: z.string().min(1).max(120).optional(),
    jobIds: z.array(z.string().min(1).max(100)).max(200).optional(),
  })
  .strict();
const deleteExternalSchema = z
  .object({ externalBatchId: z.string().min(1).max(120) })
  .strict();
const revealSchema = z.object({ path: z.string().min(1).max(4096) }).strict();

function removeQuietly(filePath: string): void {
  try {
    fs.rmSync(filePath, { force: true });
  } catch {
    // A locked file is left for the next retry; the render writes a unique name.
  }
}

function removeSiblings(filePath: string): void {
  const directory = path.dirname(filePath);
  const base = path.basename(filePath, path.extname(filePath)).replace(/ \(\d+\)$/, "");
  let entries: string[] = [];
  try {
    entries = fs.readdirSync(directory);
  } catch {
    return;
  }
  for (const name of entries) {
    if (!/\.mp4$/i.test(name)) continue;
    const stem = path.basename(name, path.extname(name)).replace(/ \(\d+\)$/, "");
    if (stem === base) removeQuietly(path.join(directory, name));
  }
}

function removeTrackVariants(job: { outputDir: string; title: string; output: string | null }): void {
  const title = String(job.title || "").trim().replace(/^\d+\.\s*/, "").toLowerCase();
  const targets = new Set<string>();
  if (job.output) targets.add(path.basename(job.output, path.extname(job.output)).replace(/ \(\d+\)$/, ""));
  let entries: string[] = [];
  try {
    entries = fs.readdirSync(job.outputDir);
  } catch {
    return;
  }
  for (const name of entries) {
    if (!/\.mp4$/i.test(name)) continue;
    const stem = path.basename(name, path.extname(name));
    const normalized = stem
      .replace(/^\d+\.\s*/, "")
      .replace(/ - reel$/i, "")
      .replace(/ \(\d+\)$/, "")
      .trim()
      .toLowerCase();
    const base = stem.replace(/ \(\d+\)$/, "");
    if ((title && normalized === title) || targets.has(base)) {
      removeQuietly(path.join(job.outputDir, name));
    }
  }
}

function removeAllMp4(directory: string): void {
  let entries: string[] = [];
  try {
    entries = fs.readdirSync(directory);
  } catch {
    return;
  }
  for (const name of entries) {
    if (/\.mp4$/i.test(name)) removeQuietly(path.join(directory, name));
  }
}

function templateNameOf(root: string, id: string): string {
  try {
    return readVideoTemplate(root, id).name;
  } catch {
    return id;
  }
}

function batchInfo(store: Store, batchId: string): PipelineBatchInfo | null {
  const record = store.getBatch(batchId);
  if (!record) return null;
  const jobs = jobsForBatch(store, batchId);
  return {
    batchId,
    outputDir: record.outputDir,
    merge: record.merge,
    mergedOutput: record.mergedOutput,
    status: record.status as PipelineBatchInfo["status"],
    error: record.error,
    total: jobs.length,
    done: jobs.filter((job) => job.status === "done").length,
    failed: jobs.filter((job) => job.status === "failed").length,
    cancelled: jobs.filter((job) => job.status === "cancelled").length,
    running: jobs.some(
      (job) => job.status === "queued" || job.status === "rendering" || job.status === "encoding",
    ),
    createdAt: record.createdAt,
    updatedAt: record.updatedAt,
  };
}

function snapshotOf(
  store: Store,
  root: string,
  running: boolean,
  error: string | null,
  auto?: PipelineAutoStatus,
): PipelineSnapshot {
  const jobs: PipelineJobInfo[] = listQueue(store).map((job) => ({
    id: job.id,
    batchId: job.batchId,
    branch: job.branch,
    templateId: job.templateId,
    templateName: templateNameOf(root, job.templateId),
    audioPath: job.audioPath,
    audioName: path.basename(job.audioPath),
    title: job.title,
    artist: job.artist,
    album: job.album,
    outputDir: job.outputDir,
    backgroundPath: job.backgroundPath,
    status: job.status,
    stage: job.stage,
    progress: job.progress,
    error: job.error,
    output: job.output,
    merge: job.merge,
    createdAt: job.createdAt,
    updatedAt: job.updatedAt,
  }));
  const batches = store
    .listBatches()
    .map((record) => batchInfo(store, record.batchId))
    .filter((batch): batch is PipelineBatchInfo => batch !== null);
  return { running, jobs, batches, error, auto };
}

export interface PipelineIpcOptions {
  host: VizzyHost;
  getWindow: () => BrowserWindow | null;
}

export function registerPipelineIpc(options: PipelineIpcOptions): void {
  const store = getStore();
  const paths = getAppPaths();
  const getShellWindow = options.getWindow;
  const shellOnly = (senderId: number): boolean => {
    const window = getShellWindow();
    const contents = window?.webContents;
    return Boolean(contents && !contents.isDestroyed() && contents.id === senderId);
  };

  let lastError: string | null = null;
  let notifyTimer: NodeJS.Timeout | null = null;

  // A restart cannot still be rendering: reconcile before the shell can read.
  const reconciled = reconcileInterruptedJobs(store);
  if (reconciled > 0) logger.warn("pipeline recovered interrupted renders", { rows: reconciled });

  const notify = (): void => {
    if (notifyTimer) return;
    notifyTimer = setTimeout(() => {
      notifyTimer = null;
      const window = getShellWindow();
      if (!window || window.webContents.isDestroyed()) return;
      const batchId = listQueue(store)[0]?.batchId ?? "";
      window.webContents.send("pipeline:changed", { batchId, reason: "progress" });
    }, 150);
  };

  const runner = new PipelineRunner({
    store,
    readTemplate: (id) => {
      const detail = readVideoTemplate(paths.templates, id);
      return {
        id: detail.id,
        name: detail.name,
        projectJson: detail.projectJson,
        pipeline: detail.pipeline,
      };
    },
    probeDuration: async (filePath) => {
      const result = await probe(filePath);
      return result.durationSec;
    },
    probeMedia: async (filePath) => {
      const result = await probe(filePath);
      return {
        durationSec: result.durationSec,
        width: result.width,
        height: result.height,
        videoCodec: result.videoCodec,
        audioCodec: result.audioCodec,
      };
    },
    render: async (input) => {
      const trackMatch = path.basename(input.job.audioPath).match(/^(\d+)\.\s*/);
      const trackPrefix = trackMatch ? `${trackMatch[1]}. ` : "";
      const title = input.outputName.replace(/^\d+\.\s*/, "");
      const fileStem = `${trackPrefix}${title}${input.job.branch === "reel" ? " - Reel" : ""}`;
      const outcome = await options.host.renderTemplateOffscreen({
        projectJson: input.plan.projectJson,
        name: input.templateName,
        audioPath: input.job.audioPath,
        outputName: input.outputName,
        outputDir: input.job.outputDir,
        fileStem,
        settings: {
          width: input.plan.settings.width,
          height: input.plan.settings.height,
          fps: input.plan.settings.fps,
          format: "mp4",
          codec: "h264",
          engine: input.plan.settings.engine,
          bitrate: input.plan.settings.bitrate,
          crf: input.plan.settings.crf,
          preset: input.plan.settings.preset,
          profile: input.plan.settings.profile,
          audioBitrate: input.plan.settings.audioBitrate,
          start: input.plan.settings.start,
          end: input.plan.settings.end,
        },
        onProgress: (progress) => {
          input.onProgress?.({
            percent: queueProgressFor(progress.done, progress.total, progress.stage),
            stage: queueStageFor(progress.stage),
          });
        },
        onStarted: (jobId) => {
          input.registerCancel?.(() => {
            options.host.cancelExport(jobId);
          });
        },
        shouldAbort: input.isCancelled,
      });
      input.registerCancel?.(null);
      if (outcome.status === "cancelled") throw new PipelineCancelledError();
      if (outcome.status === "failed") throw new Error(outcome.message);
      return { output: outcome.result.path, bytes: outcome.result.bytes };
    },
    merge: async (outputs, output) => {
      const merged = await mergeWithFallback(outputs, output);
      return { output: merged };
    },
    toMediaUrl: (filePath) => {
      try {
        allowPickedFile(filePath);
        return createMediaUrl(filePath);
      } catch (error) {
        logger.warn("pipeline media url failed", { error: String(error) });
        return null;
      }
    },
    onEvent: (event) => {
      logger.info("pipeline event", { batchId: event.batchId, reason: event.reason });
      notify();
    },
  });

  const startInBackground = (): void => {
    if (runner.isRunning()) return;
    void runner
      .run()
      .catch((error: unknown) => {
        lastError = error instanceof Error ? error.message : String(error);
        logger.error("pipeline run failed", { error: lastError });
        notify();
      })
      .finally(() => {
        notify();
        // Release the hidden window when nothing is left to render.
        const pending = listQueue(store).some((job) => job.status === "queued");
        if (!pending) options.host.disposeRenderer();
      });
  };

  // Auto-video: watch Progress rows and enqueue the next ready branch. It is
  // independent of the visible page, so a batch can finish while the user is
  // elsewhere. Settings/Profiles/templates are cached for a minute.
  const autoVideo = new AutoVideoCoordinator({
    store,
    templatesRoot: paths.templates,
    isRunnerRunning: () => runner.isRunning(),
    startRunner: startInBackground,
    onChanged: notify,
    log: (level, message, detail) => logger[level](message, detail),
  });
  const autoVideoDisabled =
    process.env.CAMXORA_DISABLE_AUTO_VIDEO === "1" ||
    (process.env.CAMXORA_E2E === "1" && process.env.CAMXORA_AUTO_VIDEO !== "1");
  if (!autoVideoDisabled) autoVideo.start();
  app.on("before-quit", () => autoVideo.stop());

  ipcMain.handle("pipeline:list", (event) => {
    if (!shellOnly(event.sender.id)) return fail("FORBIDDEN", "Wrong sender for this channel.");
    try {
      return ok(snapshotOf(store, paths.templates, runner.isRunning(), lastError, autoVideo.status()));
    } catch (error) {
      return toError(error);
    }
  });

  ipcMain.handle("pipeline:enqueue", async (event, payload: unknown) => {
    if (!shellOnly(event.sender.id)) return fail("FORBIDDEN", "Wrong sender for this channel.");
    let request: z.infer<typeof enqueueSchema>;
    try {
      request = enqueueSchema.parse(payload);
    } catch {
      return fail("INVALID_REQUEST", "The render request is not valid.");
    }

    let result: PipelineEnqueueResult;
    try {
      result = enqueuePipelineRequest({
        store,
        templatesRoot: paths.templates,
        request,
      });
    } catch (error) {
      return fail(
        "OUTPUT_DIR_INVALID",
        error instanceof Error ? error.message : "The output folder is not usable.",
      );
    }

    if (result.created > 0 && request.autostart) {
      result.started = true;
      startInBackground();
    }
    notify();
    return ok(result);
  });

  ipcMain.handle("pipeline:start", (event) => {
    if (!shellOnly(event.sender.id)) return fail("FORBIDDEN", "Wrong sender for this channel.");
    if (runner.isRunning()) return ok({ started: false, running: true });
    const queued = listQueue(store).filter((job) => job.status === "queued");
    if (queued.length === 0) {
      return fail("PIPELINE_EMPTY", "There is no queued render to start.");
    }
    lastError = null;
    startInBackground();
    return ok({ started: true, running: true });
  });

  ipcMain.handle("pipeline:cancel", (event) => {
    if (!shellOnly(event.sender.id)) return fail("FORBIDDEN", "Wrong sender for this channel.");
    const outcome = runner.cancel();
    notify();
    return ok(outcome);
  });

  ipcMain.handle("pipeline:retry", (event, payload: unknown) => {
    if (!shellOnly(event.sender.id)) return fail("FORBIDDEN", "Wrong sender for this channel.");
    let batchId: string | undefined;
    try {
      batchId = retrySchema.parse(payload ?? {}).batchId;
    } catch {
      return fail("INVALID_REQUEST", "The retry request is not valid.");
    }
    if (runner.isRunning()) {
      return fail("PIPELINE_BUSY", "Cancel the running batch before retrying.");
    }
    const failed = retryableJobs(store, batchId);
    if (failed.length === 0) {
      return fail("PIPELINE_NOTHING_TO_RETRY", "There is no failed render to retry.");
    }
    const created = enqueuePipelineJobs(
      store,
      failed.map((job) => ({
        batchId: job.batchId,
        branch: job.branch,
        templateId: job.templateId,
        audioPath: job.audioPath,
        backgroundPath: job.backgroundPath,
        logoPath: job.logoPath,
        outputDir: job.outputDir,
        title: job.title,
        artist: job.artist,
        album: job.album,
        merge: job.merge,
      })),
    );
    if (created.length === 0) {
      return fail("PIPELINE_NOTHING_TO_RETRY", "Those renders could not be re-queued.");
    }
    lastError = null;
    startInBackground();
    return ok({ enqueued: created.length, started: true });
  });

  ipcMain.handle("pipeline:force", (event, payload: unknown) => {
    if (!shellOnly(event.sender.id)) return fail("FORBIDDEN", "Wrong sender for this channel.");
    let input: z.infer<typeof forceSchema>;
    try {
      input = forceSchema.parse(payload);
    } catch {
      return fail("INVALID_REQUEST", "The regenerate request is not valid.");
    }
    if (runner.isRunning()) {
      return fail("PIPELINE_BUSY", "Cancel the running batch before regenerating.");
    }
    const ids = new Set(input.jobIds ?? []);
    const jobs = listQueue(store).filter(
      (job) =>
        (input.batchId ? job.batchId === input.batchId : true) &&
        (ids.size === 0 || ids.has(job.id)),
    );
    const broken = (job: (typeof jobs)[number]): boolean => {
      if (job.status === "failed" || job.status === "cancelled") return true;
      if (!job.output) return true;
      try {
        return fs.statSync(job.output).size <= 0;
      } catch {
        return true;
      }
    };
    const selected =
      input.mode === "force"
        ? jobs
        : input.mode === "repair"
          ? jobs.filter(broken)
          : jobs.filter((job) => ids.has(job.id));
    if (selected.length === 0) {
      return fail("PIPELINE_NOTHING_TO_RETRY", "There is no render to regenerate.");
    }
    const touchedBatches = new Set<string>();
    const outputDirs = new Set(selected.map((job) => job.outputDir));
    if (input.mode === "force") {
      // A force rebuild owns the run folder: remove every previous MP4 so a
      // regenerate can never leave an old take or a duplicate.
      for (const directory of outputDirs) removeAllMp4(directory);
    } else {
      for (const job of selected) removeTrackVariants(job);
    }
    for (const job of selected) {
      if (job.output) removeQuietly(job.output);
      updateQueueJob(store, job.id, {
        status: "queued",
        stage: "queued",
        progress: 0,
        error: null,
        output: null,
      });
      touchedBatches.add(job.batchId);
    }
    for (const batchId of touchedBatches) {
      const batch = store.getBatch(batchId);
      if (!batch) continue;
      if (batch.mergedOutput) {
        removeQuietly(batch.mergedOutput);
        removeSiblings(batch.mergedOutput);
      }
      store.upsertBatch({ ...batch, status: "idle", mergedOutput: null, error: null, updatedAt: Date.now() });
    }
    lastError = null;
    startInBackground();
    return ok({ enqueued: selected.length, started: true });
  });

  ipcMain.handle("pipeline:delete-external", (event, payload: unknown) => {
    if (!shellOnly(event.sender.id)) return fail("FORBIDDEN", "Wrong sender for this channel.");
    let input: z.infer<typeof deleteExternalSchema>;
    try {
      input = deleteExternalSchema.parse(payload);
    } catch {
      return fail("INVALID_REQUEST", "The delete request is not valid.");
    }
    if (runner.isRunning()) {
      return fail("PIPELINE_BUSY", "Cancel the running render before deleting its batch.");
    }
    const prefix = `${input.externalBatchId}:`;
    const jobs = listQueue(store).filter((job) => job.batchId.startsWith(prefix));
    const dirs = new Set(jobs.map((job) => job.outputDir));
    for (const directory of dirs) removeAllMp4(directory);
    for (const job of jobs) {
      if (job.output) removeQuietly(job.output);
      store.deleteJob(job.id);
    }
    for (const batch of store.listBatches()) {
      if (!batch.batchId.startsWith(prefix)) continue;
      if (batch.mergedOutput) {
        removeQuietly(batch.mergedOutput);
        removeSiblings(batch.mergedOutput);
      }
      store.deleteBatch(batch.batchId);
    }
    notify();
    return ok({ removed: jobs.length });
  });

  ipcMain.handle("pipeline:clear", (event) => {
    if (!shellOnly(event.sender.id)) return fail("FORBIDDEN", "Wrong sender for this channel.");
    const removed = clearFinishedJobs(store);
    if (!runner.isRunning()) {
      for (const batch of store.listBatches()) {
        if (jobsForBatch(store, batch.batchId).length === 0) store.deleteBatch(batch.batchId);
      }
    }
    notify();
    return ok({ removed });
  });

  ipcMain.handle("pipeline:reveal", (event, payload: unknown) => {
    if (!shellOnly(event.sender.id)) return fail("FORBIDDEN", "Wrong sender for this channel.");
    let target: string;
    try {
      target = revealSchema.parse(payload).path;
    } catch {
      return fail("INVALID_REQUEST", "The reveal request is not valid.");
    }
    const known = new Set<string>();
    for (const job of listQueue(store)) if (job.output) known.add(path.resolve(job.output));
    for (const batch of store.listBatches()) {
      if (batch.mergedOutput) known.add(path.resolve(batch.mergedOutput));
    }
    const resolved = path.resolve(target);
    if (!known.has(resolved) || !fs.existsSync(resolved)) {
      return fail("PIPELINE_OUTPUT_NOT_FOUND", "That render is no longer available.");
    }
    shell.showItemInFolder(resolved);
    return ok(true);
  });
}

/** `-c copy` when the batch shares encoder settings; re-encode is the fallback. */
async function mergeWithFallback(inputs: string[], output: string): Promise<string> {
  try {
    const result = await mergeVideos(planConcat(inputs, output, "copy"));
    return result.output;
  } catch (error) {
    logger.warn("pipeline merge copy failed; re-encoding", { error: String(error) });
    const fallback = uniqueOutputPath(path.dirname(output), `${path.basename(output, ".mp4")}-rec`);
    const result = await mergeVideos(planConcat(inputs, fallback, "reencode"));
    return result.output;
  }
}
