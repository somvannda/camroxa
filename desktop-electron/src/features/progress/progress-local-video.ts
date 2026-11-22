import type { PipelineSnapshot } from "../../../electron/shared/types";
import type { ProgressRow } from "./progress-types";

export interface LocalVideoSummary {
  /** Jobs that belong to this operational row's batch/branch. */
  total: number;
  done: number;
  failed: number;
  cancelled: number;
  running: boolean;
  percent: number;
  status: "none" | "queued" | "rendering" | "done" | "failed" | "merged";
  /** Video (Render) cell. */
  videoPrimary: string | null;
  videoSecondary: string | null;
  /** Merge cell. */
  mergePrimary: string | null;
  mergeSecondary: string | null;
  /** A representative rendered file and merged file to reveal. */
  outputPath: string | null;
  mergedPath: string | null;
  /** Pipeline batch id that can be retried. */
  retryBatchId: string | null;
  /** Jobs represented by this row, for single-track regeneration. */
  jobs: Array<{ id: string; title: string; status: string }>;
  /** Newest local queue update, for the Updated column. */
  updatedAt: number | null;
}

const EMPTY: LocalVideoSummary = {
  total: 0,
  done: 0,
  failed: 0,
  cancelled: 0,
  running: false,
  percent: 0,
  status: "none",
  videoPrimary: null,
  videoSecondary: null,
  mergePrimary: null,
  mergeSecondary: null,
  outputPath: null,
  mergedPath: null,
  retryBatchId: null,
  jobs: [],
  updatedAt: null,
};

function baseName(filePath: string): string {
  const parts = filePath.split(/[\\/]/);
  return parts[parts.length - 1] || filePath;
}

/**
 * Fold the local durable render queue into one operational row.
 *
 * The queue is keyed `<batch>:<branch>`; rows are per channel, so the job album
 * disambiguates Primary from Secondary without changing the queue schema.
 */
export function localVideoForRow(
  row: ProgressRow,
  snapshot: PipelineSnapshot | null | undefined,
): LocalVideoSummary {
  if (!snapshot) return EMPTY;
  const batchId = String(row.meta.batch_id || row.batch || "").trim();
  if (!batchId) return EMPTY;
  const album = String(row.album ?? "").trim().toLowerCase();

  const jobs = snapshot.jobs.filter((job) => {
    if (!job.batchId.startsWith(`${batchId}:`)) return false;
    if (!album) return true;
    const jobAlbum = String(job.album ?? "").trim().toLowerCase();
    return !jobAlbum || jobAlbum === album;
  });
  if (jobs.length === 0) return EMPTY;

  const batches = snapshot.batches.filter((batch) => jobBatchIds(jobs).has(batch.batchId));
  const done = jobs.filter((job) => job.status === "done").length;
  const failed = jobs.filter((job) => job.status === "failed").length;
  const cancelled = jobs.filter((job) => job.status === "cancelled").length;
  const running = jobs.some(
    (job) => job.status === "rendering" || job.status === "encoding" || job.status === "queued",
  );
  const percent = Math.round(
    jobs.reduce((sum, job) => sum + (job.status === "done" ? 100 : job.progress), 0) /
      Math.max(1, jobs.length),
  );
  const merged = batches.find((batch) => Boolean(batch.mergedOutput)) ?? null;
  const mergeFailed = batches.some((batch) => batch.status === "failed" && batch.merge);

  let status: LocalVideoSummary["status"] = "queued";
  if (failed > 0) status = "failed";
  else if (merged) status = "merged";
  else if (done === jobs.length) status = "done";
  else if (running) status = "rendering";

  const videoPrimary = merged
    ? baseName(merged.mergedOutput ?? "")
    : `${done}/${jobs.length} rendered`;
  const videoSecondary = merged
    ? "Merged"
    : failed > 0
      ? `${failed} failed`
      : running
        ? `Rendering ${percent}%`
        : done === jobs.length
          ? "Ready to merge"
          : "Waiting to render";

  return {
    total: jobs.length,
    done,
    failed,
    cancelled,
    running,
    percent,
    status,
    videoPrimary,
    videoSecondary,
    mergePrimary: merged
      ? baseName(merged.mergedOutput ?? "")
      : mergeFailed
        ? "Merge failed"
        : done === jobs.length
          ? "Ready to merge"
          : null,
    mergeSecondary: merged ? "Merged" : null,
    outputPath: jobs.find((job) => job.output)?.output ?? null,
    mergedPath: merged?.mergedOutput ?? null,
    retryBatchId:
      failed > 0 || cancelled > 0
        ? (jobs.find((job) => job.status === "failed" || job.status === "cancelled")?.batchId ??
          null)
        : null,
    jobs: jobs.map((job) => ({ id: job.id, title: job.title, status: job.status })),
    updatedAt: Math.max(...jobs.map((job) => job.updatedAt || 0)) || null,
  };
}

function jobBatchIds(jobs: Array<{ batchId: string }>): Set<string> {
  return new Set(jobs.map((job) => job.batchId));
}
