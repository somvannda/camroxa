/**
 * Shared enqueue path for both the shell IPC handler and the auto-video
 * coordinator.
 *
 * Resolves the run audio, validates the template and its branch, and creates
 * the durable queue rows. Notification, starting the runner and IPC envelopes
 * stay with the caller.
 */
import crypto from "node:crypto";
import fs from "node:fs";
import path from "node:path";
import type {
  PipelineEnqueueRequest,
  PipelineEnqueueResult,
} from "../shared/types";
import type { Store } from "./database";
import { enqueuePipelineJobs, type PipelineQueueInput } from "./pipeline-queue";
import { findAudioForSong } from "./pipeline-sources";
import { readVideoTemplate } from "./video-templates";

export interface EnqueuePipelineOptions {
  store: Store;
  templatesRoot: string;
  request: PipelineEnqueueRequest;
}

export function enqueuePipelineRequest(
  options: EnqueuePipelineOptions,
): PipelineEnqueueResult {
  const { store, templatesRoot, request } = options;
  const result: PipelineEnqueueResult = {
    batchId: request.batchId ?? crypto.randomUUID(),
    created: 0,
    skipped: 0,
    duplicates: 0,
    skippedDetails: [],
    started: false,
    message: null,
  };

  let outputDir: string;
  try {
    outputDir = path.resolve(request.outputDir);
    fs.mkdirSync(outputDir, { recursive: true });
  } catch (error) {
    throw new Error(`The output folder is not usable: ${String(error)}`);
  }

  const now = Date.now();
  const existing = store.getBatch(result.batchId);
  store.upsertBatch({
    batchId: result.batchId,
    outputDir,
    merge: request.merge === true || existing?.merge === true,
    mergedOutput: existing?.mergedOutput ?? null,
    status: "idle",
    error: null,
    createdAt: existing?.createdAt ?? now,
    updatedAt: now,
  });

  const inputs: PipelineQueueInput[] = [];
  for (const job of request.jobs) {
    let detail: ReturnType<typeof readVideoTemplate>;
    try {
      detail = readVideoTemplate(templatesRoot, job.templateId);
    } catch {
      result.skippedDetails.push({
        audioPath: job.audioPath ?? "",
        title: job.title ?? "",
        reason: `Template "${job.templateId}" is missing. Choose a saved template in Settings.`,
      });
      continue;
    }
    if (detail.pipeline.kind !== job.branch) {
      result.skippedDetails.push({
        audioPath: job.audioPath ?? "",
        title: job.title ?? "",
        reason: `"${detail.name}" is a ${detail.pipeline.kind} template, not ${job.branch}.`,
      });
      continue;
    }

    let audioPath = job.audioPath?.trim() ?? "";
    if (!audioPath && job.audioDir) {
      const found = findAudioForSong(job.audioDir, job.title ?? "", job.audioBranch ?? "ok", {
        allowOnlyFile: true,
      });
      if (!found.ok) {
        result.skippedDetails.push({
          audioPath: job.audioDir,
          title: job.title ?? "",
          reason: found.reason,
        });
        continue;
      }
      audioPath = found.path;
    }
    if (!audioPath) {
      result.skippedDetails.push({
        audioPath: job.audioDir ?? "",
        title: job.title ?? "",
        reason: "The song has no audio file yet.",
      });
      continue;
    }
    try {
      const stat = fs.statSync(path.resolve(audioPath));
      if (!stat.isFile() || stat.size <= 0) throw new Error("not a file");
    } catch {
      result.skippedDetails.push({
        audioPath,
        title: job.title ?? "",
        reason: "The audio file is missing or empty.",
      });
      continue;
    }

    inputs.push({
      batchId: result.batchId,
      branch: job.branch,
      templateId: job.templateId,
      audioPath: path.resolve(audioPath),
      backgroundPath: job.backgroundPath,
      logoPath: job.logoPath,
      outputDir,
      title: job.title ?? "",
      artist: job.artist ?? "",
      album: job.album ?? "",
      merge: request.merge === true,
    });
  }

  const created = enqueuePipelineJobs(store, inputs);
  result.created = created.length;
  result.skipped = result.skippedDetails.length;
  result.duplicates = inputs.length - created.length;
  if (result.created === 0) {
    result.message =
      result.skippedDetails[0]?.reason ??
      (result.duplicates > 0
        ? "These renders are already queued or done."
        : "Nothing was ready to render.");
    if (result.skipped === 0 && result.duplicates === 0) {
      store.deleteBatch(result.batchId);
    }
  } else {
    result.message = `${result.created} render${result.created === 1 ? "" : "s"} queued.`;
  }
  return result;
}
