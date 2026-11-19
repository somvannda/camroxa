import type {
  PipelineBatchInfo,
  PipelineJobInfo,
  PipelineJobStatus,
} from "../../../electron/shared/types";

export type PipelineTone = "neutral" | "success" | "warning" | "danger" | "accent";

export function pipelineStatusLabel(status: PipelineJobStatus): string {
  switch (status) {
    case "queued":
      return "Queued";
    case "rendering":
      return "Rendering";
    case "encoding":
      return "Encoding";
    case "merging":
      return "Merging";
    case "done":
      return "Done";
    case "failed":
      return "Failed";
    case "cancelled":
      return "Cancelled";
    default:
      return status;
  }
}

export function pipelineStatusTone(status: PipelineJobStatus): PipelineTone {
  if (status === "done") return "success";
  if (status === "failed") return "danger";
  if (status === "cancelled") return "warning";
  if (status === "queued") return "neutral";
  return "accent";
}

export function pipelineBranchLabel(job: PipelineJobInfo): string {
  return job.branch === "reel" ? "Reel" : "Long video";
}

/** Stage text the row shows under the status badge. */
export function pipelineStageText(job: PipelineJobInfo): string {
  if (job.status === "done") return "Validated";
  if (job.status === "failed") return "Needs attention";
  if (job.status === "cancelled") return "Stopped";
  if (job.status === "queued") return "Waiting to render";
  return job.stage;
}

export function pipelineProgressText(job: PipelineJobInfo): string {
  if (job.status === "done") return "100%";
  if (job.status === "failed" || job.status === "cancelled") return "—";
  return `${Math.max(0, Math.min(100, Math.round(job.progress)))}%`;
}

export function pipelineBatchLabel(batch: PipelineBatchInfo): string {
  if (batch.status === "merging") return "Merging";
  if (batch.status === "failed") return "Failed";
  if (batch.status === "cancelled") return "Cancelled";
  if (batch.status === "running") return "Running";
  if (batch.status === "done") return "Complete";
  return "Idle";
}

/** `2 done · 1 failed` — never implies work that did not happen. */
export function pipelineBatchCounts(batch: PipelineBatchInfo): string {
  const parts: string[] = [];
  if (batch.done > 0) parts.push(`${batch.done} done`);
  if (batch.failed > 0) parts.push(`${batch.failed} failed`);
  if (batch.cancelled > 0) parts.push(`${batch.cancelled} cancelled`);
  const pending = batch.total - batch.done - batch.failed - batch.cancelled;
  if (pending > 0) parts.push(`${pending} pending`);
  return parts.length ? parts.join(" · ") : "No renders";
}

export function pipelineSummaryText(snapshot: {
  jobs: PipelineJobInfo[];
  batches: PipelineBatchInfo[];
}): string {
  const total = snapshot.jobs.length;
  if (total === 0) return "No video renders yet.";
  const done = snapshot.jobs.filter((job) => job.status === "done").length;
  const failed = snapshot.jobs.filter((job) => job.status === "failed").length;
  const running = snapshot.jobs.filter(
    (job) => job.status === "rendering" || job.status === "encoding",
  ).length;
  const queued = snapshot.jobs.filter((job) => job.status === "queued").length;
  const merged = snapshot.batches.filter((batch) => batch.mergedOutput).length;
  const parts = [`${done}/${total} rendered`];
  if (running > 0) parts.push(`${running} running`);
  if (queued > 0) parts.push(`${queued} queued`);
  if (failed > 0) parts.push(`${failed} failed`);
  if (merged > 0) parts.push(`${merged} merged`);
  return parts.join(" · ");
}
