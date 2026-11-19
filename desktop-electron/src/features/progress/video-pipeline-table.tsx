import { Link } from "react-router-dom";
import { Button } from "../../components/button";
import { Card } from "../../components/card";
import { Icon } from "../../components/icon";
import { Badge } from "../../components/status";
import { TBody, TD, TH, THead, TR } from "../../components/table";
import { classNames } from "../../lib/format";
import type { PipelineBatchInfo, PipelineJobInfo } from "../../../electron/shared/types";
import { useVideoPipeline } from "./use-video-pipeline";
import {
  pipelineBatchCounts,
  pipelineBatchLabel,
  pipelineBranchLabel,
  pipelineProgressText,
  pipelineStageText,
  pipelineStatusLabel,
  pipelineStatusTone,
  pipelineSummaryText,
  type PipelineTone,
} from "./video-pipeline-format";

function baseName(filePath: string): string {
  const parts = filePath.split(/[\\/]/);
  return parts[parts.length - 1] || filePath;
}

function BatchCard({
  batch,
  onReveal,
}: {
  batch: PipelineBatchInfo;
  onReveal: (filePath: string) => void;
}) {
  const tone: PipelineTone =
    batch.status === "failed"
      ? "danger"
      : batch.status === "running" || batch.status === "merging"
        ? "accent"
        : batch.status === "cancelled"
          ? "warning"
          : batch.status === "done"
            ? "success"
            : "neutral";
  return (
    <div
      className="flex flex-wrap items-center gap-x-3 gap-y-1 border-t border-border px-4 py-2"
      data-testid="pipeline-batch"
    >
      <span className="font-mono text-meta text-text-primary">{batch.batchId}</span>
      <Badge tone={tone}>{pipelineBatchLabel(batch)}</Badge>
      <span className="text-caption text-text-secondary">{pipelineBatchCounts(batch)}</span>
      {batch.merge ? (
        <span className="text-caption text-text-muted">
          {batch.mergedOutput ? "Merged" : batch.status === "merging" ? "Merging…" : "Merge requested"}
        </span>
      ) : null}
      {batch.mergedOutput ? (
        <button
          type="button"
          className="inline-flex max-w-[320px] items-center gap-1 truncate text-caption text-accent hover:underline"
          title={batch.mergedOutput}
          onClick={() => onReveal(batch.mergedOutput ?? "")}
          data-testid="pipeline-merged-reveal"
        >
          <Icon name="fa-folder-open" size={12} />
          <span className="truncate">{baseName(batch.mergedOutput)}</span>
        </button>
      ) : null}
      {batch.error ? (
        <span className="text-caption text-danger" role="status">
          {batch.error}
        </span>
      ) : null}
    </div>
  );
}

function ProgressBar({ value }: { value: number }) {
  const percent = Math.max(0, Math.min(100, Math.round(value)));
  return (
    <div className="flex items-center gap-2">
      <div className="h-1.5 w-24 overflow-hidden rounded-full bg-surface-3">
        <div
          className={classNames("h-full rounded-full", percent >= 100 ? "bg-success" : "bg-accent")}
          style={{ width: `${percent}%` }}
        />
      </div>
      <span className="text-caption text-text-muted">{percent}%</span>
    </div>
  );
}

function JobRow({
  job,
  busy,
  running,
  onRetry,
  onReveal,
  onCancel,
}: {
  job: PipelineJobInfo;
  busy: boolean;
  running: boolean;
  onRetry: (job: PipelineJobInfo) => void;
  onReveal: (filePath: string) => void;
  onCancel: () => void;
}) {
  const retryable = job.status === "failed" || job.status === "cancelled";
  const cancellable =
    running && (job.status === "rendering" || job.status === "encoding");
  return (
    <TR data-testid="pipeline-row" data-status={job.status} data-job-id={job.id}>
      <TD className="py-2 align-top">
        <Badge tone={pipelineStatusTone(job.status)}>{pipelineStatusLabel(job.status)}</Badge>
        <p className="mt-0.5 truncate text-caption text-text-muted" data-testid="pipeline-stage">
          {pipelineStageText(job)}
        </p>
      </TD>
      <TD className="py-2 align-top">
        <span className="block max-w-[180px] truncate" title={job.templateName}>
          {job.templateName || job.templateId}
        </span>
        <p className="mt-0.5 text-caption text-text-muted">{pipelineBranchLabel(job)}</p>
      </TD>
      <TD className="py-2 align-top">
        <span className="block max-w-[200px] truncate" title={job.title || job.audioName}>
          {job.title || job.audioName}
        </span>
        <p className="mt-0.5 max-w-[200px] truncate text-caption text-text-muted" title={job.audioPath}>
          {job.audioName}
        </p>
      </TD>
      <TD className="py-2 align-top">
        {job.status === "done" || job.status === "failed" ? (
          <span className="text-meta" data-testid="pipeline-progress">
            {pipelineProgressText(job)}
          </span>
        ) : (
          <div data-testid="pipeline-progress">
            <ProgressBar value={job.progress} />
          </div>
        )}
      </TD>
      <TD className="py-2 align-top">
        <span
          className={classNames(
            "block max-w-[240px] truncate text-meta",
            job.error ? "text-danger" : "text-text-muted",
          )}
          title={job.error ?? undefined}
          data-testid="pipeline-error"
        >
          {job.error ?? "—"}
        </span>
      </TD>
      <TD className="py-2 align-top">
        <div className="flex items-center gap-1.5">
          {job.output ? (
            <Button
              variant="ghost"
              className="h-7 px-2"
              onClick={() => onReveal(job.output ?? "")}
              data-testid="pipeline-reveal"
            >
              <Icon name="fa-folder-open" size={12} />
              Reveal
            </Button>
          ) : null}
          {cancellable ? (
            <Button
              variant="secondary"
              className="h-7 px-2"
              disabled={busy}
              onClick={onCancel}
              data-testid="pipeline-cancel"
            >
              Cancel
            </Button>
          ) : null}
          {retryable ? (
            <Button
              variant="secondary"
              className="h-7 px-2"
              disabled={busy}
              onClick={() => onRetry(job)}
              data-testid="pipeline-retry"
            >
              Retry
            </Button>
          ) : null}
        </div>
      </TD>
    </TR>
  );
}

/**
 * Compact "Video pipeline" section on Progress.
 *
 * It reads the durable queue, so it survives a route change and an app restart.
 * Cancel and Retry call the real IPC handlers; there are no decorative actions.
 */
export function VideoPipelineSection() {
  const pipeline = useVideoPipeline();
  const snapshot = pipeline.snapshot;
  const jobs = snapshot?.jobs ?? [];
  const batches = snapshot?.batches ?? [];
  const running = snapshot?.running === true;
  const hasRetryable = jobs.some((job) => job.status === "failed" || job.status === "cancelled");

  return (
    <Card className="overflow-hidden" data-testid="video-pipeline">
      <div className="flex items-start justify-between gap-4 border-b border-border px-4 py-3">
        <div>
          <h2 className="text-title font-semibold text-text-primary">Video pipeline</h2>
          <p className="mt-0.5 text-meta text-text-secondary">
            Queued Vizzy renders from Music. Rendering runs without opening the editor.
          </p>
        </div>
        <div className="flex shrink-0 items-center gap-2">
          <span className="font-mono text-caption text-text-muted" data-testid="pipeline-summary">
            {snapshot ? pipelineSummaryText({ jobs, batches }) : "Loading"}
          </span>
          {running ? (
            <Button
              variant="secondary"
              className="h-7 px-2"
              disabled={pipeline.busy}
              onClick={() => void pipeline.cancel()}
              data-testid="pipeline-cancel-batch"
            >
              Cancel batch
            </Button>
          ) : null}
          {hasRetryable && !running ? (
            <Button
              variant="secondary"
              className="h-7 px-2"
              disabled={pipeline.busy}
              onClick={() => void pipeline.retry()}
              data-testid="pipeline-retry-batch"
            >
              Retry failed
            </Button>
          ) : null}
          {!running && jobs.length > 0 ? (
            <Button
              variant="ghost"
              className="h-7 px-2"
              disabled={pipeline.busy}
              onClick={() => void pipeline.clear()}
              data-testid="pipeline-clear"
            >
              Clear finished
            </Button>
          ) : null}
        </div>
      </div>

      {pipeline.error ? (
        <p className="border-b border-border px-4 py-2 text-caption text-danger" role="status">
          {pipeline.error}
        </p>
      ) : null}

      {!pipeline.loading && jobs.length === 0 ? (
        <div className="px-4 py-8 text-center" data-testid="pipeline-empty">
          <p className="text-body text-text-secondary">
            No video renders yet. Turn on Auto-Video in Music and use “Render videos”.
          </p>
          <Link
            to="/music"
            className="mt-2 inline-flex items-center gap-1 text-meta text-accent hover:underline"
          >
            Open Music
            <Icon name="fa-arrow-right" size={12} />
          </Link>
        </div>
      ) : null}

      {jobs.length > 0 ? (
        <div className="max-h-[380px] overflow-auto">
          <table className="w-full min-w-[900px] table-fixed border-collapse text-body">
            <colgroup>
              <col className="w-[124px]" />
              <col className="w-[190px]" />
              <col className="w-[210px]" />
              <col className="w-[120px]" />
              <col className="w-[250px]" />
              <col className="w-[170px]" />
            </colgroup>
            <THead className="sticky top-0 z-10">
              <TR className="hover:bg-transparent">
                <TH className="bg-surface-2">Status</TH>
                <TH className="bg-surface-2">Template</TH>
                <TH className="bg-surface-2">Song</TH>
                <TH className="bg-surface-2">Progress</TH>
                <TH className="bg-surface-2">Error</TH>
                <TH className="bg-surface-2">Actions</TH>
              </TR>
            </THead>
            <TBody>
              {jobs.map((job) => (
                <JobRow
                  key={job.id}
                  job={job}
                  busy={pipeline.busy}
                  running={running}
                  onCancel={() => void pipeline.cancel()}
                  onRetry={(row) => void pipeline.retry(row.batchId)}
                  onReveal={(filePath) => void pipeline.reveal(filePath)}
                />
              ))}
            </TBody>
          </table>
        </div>
      ) : null}

      {batches.map((batch) => (
        <BatchCard
          key={batch.batchId}
          batch={batch}
          onReveal={(filePath) => void pipeline.reveal(filePath)}
        />
      ))}
    </Card>
  );
}
