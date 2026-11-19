import crypto from "node:crypto";
import type { Store } from "./database";

/**
 * Durable pipeline queue.
 *
 * The queue is intentionally small: it serialises run items into the existing
 * `pipeline_jobs` table, deduplicates identical work, and exposes the next
 * queued item. Orchestration (render/merge/reel) lives above it.
 */

export type PipelineBranch = "long" | "reel";

export type PipelineJobStatus =
  | "queued"
  | "rendering"
  | "encoding"
  | "merging"
  | "done"
  | "failed"
  | "cancelled";

export interface PipelineQueueItem {
  id: string;
  batchId: string;
  branch: PipelineBranch;
  templateId: string;
  audioPath: string;
  backgroundPath: string;
  logoPath: string;
  outputDir: string;
  title: string;
  artist: string;
  album: string;
  status: PipelineJobStatus;
  stage: string;
  progress: number;
  error: string | null;
}

export interface PipelineQueueInput {
  batchId: string;
  branch: PipelineBranch;
  templateId: string;
  audioPath: string;
  backgroundPath?: string;
  logoPath?: string;
  outputDir: string;
  title?: string;
  artist?: string;
  album?: string;
}

function keyOf(item: Pick<PipelineQueueInput, "batchId" | "branch" | "templateId" | "audioPath">) {
  return [item.batchId, item.branch, item.templateId, item.audioPath].join("\u0000");
}

function parsePayload(payload: string): PipelineQueueInput | null {
  try {
    const value = JSON.parse(payload) as Partial<PipelineQueueInput>;
    if (
      typeof value.batchId !== "string" ||
      (value.branch !== "long" && value.branch !== "reel") ||
      typeof value.templateId !== "string" ||
      typeof value.audioPath !== "string" ||
      typeof value.outputDir !== "string"
    ) {
      return null;
    }
    return {
      batchId: value.batchId,
      branch: value.branch,
      templateId: value.templateId,
      audioPath: value.audioPath,
      backgroundPath: typeof value.backgroundPath === "string" ? value.backgroundPath : "",
      logoPath: typeof value.logoPath === "string" ? value.logoPath : "",
      outputDir: value.outputDir,
      title: typeof value.title === "string" ? value.title : "",
      artist: typeof value.artist === "string" ? value.artist : "",
      album: typeof value.album === "string" ? value.album : "",
    };
  } catch {
    return null;
  }
}

export function listQueue(store: Store): PipelineQueueItem[] {
  const items: PipelineQueueItem[] = [];
  for (const job of store.listJobs()) {
    const input = parsePayload(job.payload);
    if (!input) continue;
    items.push({
      id: job.id,
      ...input,
      backgroundPath: input.backgroundPath ?? "",
      logoPath: input.logoPath ?? "",
      title: input.title ?? "",
      artist: input.artist ?? "",
      album: input.album ?? "",
      status: job.status as PipelineJobStatus,
      stage: job.stage,
      progress: job.progress,
      error: job.error,
    });
  }
  return items;
}

/**
 * enqueue adds the items that are not already queued, running or done for the
 * same `(batch, branch, template, audio)` key. Failed/cancelled items may be
 * enqueued again (retry).
 */
export function enqueuePipelineJobs(store: Store, inputs: PipelineQueueInput[]): PipelineQueueItem[] {
  const existing = listQueue(store);
  const blocked = new Set(
    existing
      .filter((item) => item.status === "queued" || item.status === "rendering" || item.status === "encoding" || item.status === "merging" || item.status === "done")
      .map((item) => keyOf(item)),
  );
  const created: PipelineQueueItem[] = [];
  const now = Date.now();
  for (const input of inputs) {
    const key = keyOf(input);
    if (blocked.has(key)) continue;
    blocked.add(key);
    const id = crypto.randomUUID();
    const normalized: PipelineQueueInput = {
      ...input,
      backgroundPath: input.backgroundPath ?? "",
      logoPath: input.logoPath ?? "",
      title: input.title ?? "",
      artist: input.artist ?? "",
      album: input.album ?? "",
    };
    store.createJob({
      id,
      batchId: input.batchId,
      status: "queued",
      stage: "queued",
      progress: 0,
      payload: JSON.stringify(normalized),
      error: null,
      createdAt: now,
      updatedAt: now,
    });
    created.push({
      id,
      ...normalized,
      backgroundPath: normalized.backgroundPath ?? "",
      logoPath: normalized.logoPath ?? "",
      title: normalized.title ?? "",
      artist: normalized.artist ?? "",
      album: normalized.album ?? "",
      status: "queued",
      stage: "queued",
      progress: 0,
      error: null,
    });
  }
  return created;
}

export function nextQueuedJob(store: Store): PipelineQueueItem | null {
  return listQueue(store).find((item) => item.status === "queued") ?? null;
}

export function updateQueueJob(
  store: Store,
  id: string,
  patch: {
    status?: PipelineJobStatus;
    stage?: string;
    progress?: number;
    error?: string | null;
  },
): void {
  store.updateJob(id, {
    ...(patch.status ? { status: patch.status } : {}),
    ...(patch.stage ? { stage: patch.stage } : {}),
    ...(typeof patch.progress === "number" ? { progress: patch.progress } : {}),
    ...(patch.error !== undefined ? { error: patch.error } : {}),
  });
}

export function clearFinishedJobs(store: Store): number {
  let removed = 0;
  for (const item of listQueue(store)) {
    if (item.status === "done" || item.status === "cancelled") {
      store.deleteJob(item.id);
      removed += 1;
    }
  }
  return removed;
}
