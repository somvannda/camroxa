import { useEffect, useState, type ReactNode } from "react";
import { Icon } from "../../components/icon";
import { Button } from "../../components/button";
import { Card } from "../../components/card";
import { Dialog, DialogContent } from "../../components/dialog";
import { Badge, StatusDot } from "../../components/status";
import { classNames } from "../../lib/format";
import { copyText } from "./progress-clipboard";
import { missingAssetHint, type ManualInspection } from "./manual-assets";
import {
  failureStageLabel,
  formatAbsoluteTime,
  localStageDisplay,
  localVideoState,
  normalizeStatus,
  notesText,
  rowKey,
  runDateLabel,
  stageKey,
  stageTimeline,
  statusLabel,
  updatedCellText,
  youtubeCellText,
  type TimelineState,
} from "./progress-format";
import { localVideoForRow } from "./progress-local-video";
import type { PipelineSnapshot } from "../../../electron/shared/types";
import type { ProgressRow } from "./progress-types";

interface ProgressDetailProps {
  row: ProgressRow;
  /** Local durable render queue, folded into the stage timeline. */
  pipeline?: PipelineSnapshot | null;
  manualMode: boolean;
  inspection: ManualInspection | undefined;
  inspecting: boolean;
  syncing: boolean;
  onClose: () => void;
  onInspect: (row: ProgressRow) => void;
  onOpenFolder: (path: string) => void;
  onReveal: (path: string) => void;
  onOpenExternal: (url: string) => void;
  onSyncManual: (row: ProgressRow) => void;
  onRetryImage: (row: ProgressRow) => Promise<string>;
  /** Manual YouTube upload surface, built by the page for this row. */
  youtubePanel?: ReactNode;
}

const TIMELINE_TONE: Record<TimelineState, "success" | "accent" | "neutral" | "danger"> = {
  passed: "success",
  current: "accent",
  pending: "neutral",
  failed: "danger",
  unavailable: "neutral",
};

function Field({ label, children, mono = false }: { label: string; children: ReactNode; mono?: boolean }) {
  return (
    <div className="min-w-0">
      <dt className="text-caption text-text-muted">{label}</dt>
      <dd className={classNames("mt-0.5 truncate", mono ? "font-mono text-meta" : "text-body")}>
        {children}
      </dd>
    </div>
  );
}

function PathRow({
  label,
  value,
  kind,
  onOpenFolder,
  onReveal,
  onOpenExternal,
}: {
  label: string;
  value: string;
  kind: "folder" | "file" | "link";
  onOpenFolder: (path: string) => void;
  onReveal: (path: string) => void;
  onOpenExternal: (url: string) => void;
}) {
  return (
    <div className="flex items-start justify-between gap-3 border-b border-border py-2 last:border-b-0">
      <div className="min-w-0">
        <p className="text-caption text-text-muted">{label}</p>
        <p className="mt-0.5 break-all font-mono text-meta text-text-secondary" title={value}>
          {value}
        </p>
      </div>
      {kind === "folder" ? (
        <Button variant="ghost" className="shrink-0" onClick={() => onOpenFolder(value)}>
          <Icon name="fa-folder-open" size={14} />
          Open folder
        </Button>
      ) : null}
      {kind === "file" ? (
        <Button variant="ghost" className="shrink-0" onClick={() => onReveal(value)}>
          <Icon name="fa-folder-open" size={14} />
          Reveal
        </Button>
      ) : null}
      {kind === "link" ? (
        <Button variant="ghost" className="shrink-0" onClick={() => onOpenExternal(value)}>
          <Icon name="fa-arrow-up-right-from-square" size={14} />
          Open link
        </Button>
      ) : null}
    </div>
  );
}

export function ProgressDetail({
  row,
  pipeline,
  manualMode,
  inspection,
  inspecting,
  syncing,
  onClose,
  onInspect,
  onOpenFolder,
  onReveal,
  onOpenExternal,
  onSyncManual,
  onRetryImage,
  youtubePanel,
}: ProgressDetailProps) {
  const [copied, setCopied] = useState(false);
  const [retryOpen, setRetryOpen] = useState(false);
  const [retrying, setRetrying] = useState(false);
  const [retryResult, setRetryResult] = useState<{ tone: "success" | "danger"; text: string } | null>(
    null,
  );

  const key = rowKey(row);
  useEffect(() => {
    setCopied(false);
    setRetryResult(null);
    setRetryOpen(false);
  }, [key]);

  useEffect(() => {
    if (!manualMode) return;
    if (inspection || inspecting) return;
    onInspect(row);
    // The inspection is keyed by row; a poll that re-binds the same run must not requeue.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [manualMode, key, inspection, inspecting]);

  const meta = row.meta;
  const video = localVideoState(row);
  const local = localVideoForRow(row, pipeline);
  const timeline = stageTimeline(row, manualMode, local);
  const stageDisplay = localStageDisplay(row, local);
  const statusDisplay = local.failed
    ? "Failed"
    : local.mergedPath
      ? "Completed"
      : local.total > 0 && local.done === local.total
        ? "Rendered"
        : local.running
          ? "Rendering"
          : statusLabel(row.status);
  const note = notesText(row);
  const failed =
    stageKey(row.stage) === "error" ||
    normalizeStatus(row.status) === "failed" ||
    normalizeStatus(row.status) === "blocked";
  const failedStage = failureStageLabel(row);
  const updated = updatedCellText(row);
  const youtube = youtubeCellText(row);

  const imageStage = stageKey(row.stage) === "image";
  const retryable = failed && imageStage && !manualMode;
  const retryReason = !failed
    ? "Retry is available when a stage fails."
    : manualMode && imageStage
      ? "Image retry is not available in manual image mode."
      : retryable
        ? null
        : `Stage retry is not available for ${failedStage ?? "this stage"} yet.`;

  const paths = [
    meta.run_dir ? { label: "Run folder", value: meta.run_dir, kind: "folder" as const } : null,
    local.mergedPath
      ? { label: "Merged video", value: local.mergedPath, kind: "file" as const }
      : null,
    local.outputPath && !local.mergedPath
      ? { label: "Rendered video", value: local.outputPath, kind: "file" as const }
      : null,
    meta.background_16x9_path
      ? { label: "Background 16:9", value: meta.background_16x9_path, kind: "file" as const }
      : null,
    meta.background_9x16_path
      ? { label: "Background 9:16", value: meta.background_9x16_path, kind: "file" as const }
      : null,
    meta.thumbnail_16x9_path
      ? { label: "Thumbnail 16:9", value: meta.thumbnail_16x9_path, kind: "file" as const }
      : null,
    meta.thumbnail_9x16_path
      ? { label: "Thumbnail 9:16", value: meta.thumbnail_9x16_path, kind: "file" as const }
      : null,
    youtube.url ? { label: "YouTube", value: youtube.url, kind: "link" as const } : null,
  ].filter((item): item is { label: string; value: string; kind: "folder" | "file" | "link" } =>
    Boolean(item),
  );

  const runRetry = async () => {
    setRetrying(true);
    setRetryOpen(false);
    try {
      const message = await onRetryImage(row);
      setRetryResult({ tone: "success", text: message });
    } catch (error) {
      setRetryResult({
        tone: "danger",
        text: error instanceof Error ? error.message : "Unable to retry the image stage.",
      });
    } finally {
      setRetrying(false);
    }
  };

  const copyRunId = async () => {
    const result = await copyText(meta.batch_id || row.batch);
    setCopied(result);
  };

  const hint = inspection ? missingAssetHint(inspection.missing) : null;

  return (
    <Card className="p-4" data-testid="progress-detail">
      <div className="flex items-start justify-between gap-4">
        <div className="min-w-0">
          <p className="text-caption text-text-muted">Row detail</p>
          <div className="mt-0.5 flex flex-wrap items-center gap-2">
            <h2 className="truncate font-mono text-title text-text-primary">
              {row.batch || "Not reported"}
            </h2>
            <Badge tone={stageDisplay.tone}>{stageDisplay.text}</Badge>
            <Badge tone={failed ? "danger" : "neutral"}>{statusDisplay}</Badge>
          </div>
        </div>
        <Button variant="ghost" aria-label="Close row detail" onClick={onClose}>
          <Icon name="fa-xmark" size={15} />
        </Button>
      </div>

      <dl className="mt-4 grid grid-cols-2 gap-4 border-y border-border py-3 xl:grid-cols-4">
        <Field label="Batch">
          <span className="flex items-center gap-2">
            <span className="truncate font-mono text-meta">{meta.batch_id || row.batch || "--"}</span>
            <button
              type="button"
              className="inline-flex h-5 w-5 shrink-0 items-center justify-center rounded-[4px] text-text-muted hover:bg-surface-hover hover:text-text-primary"
              title="Copy run id"
              aria-label="Copy run id"
              onClick={copyRunId}
            >
              <Icon name="fa-copy" size={12} />
            </button>
            {copied ? <span className="text-caption text-success">Copied</span> : null}
          </span>
        </Field>
        <Field label="Channel">
          {row.channel || "Unknown channel"} · {meta.role || "Run"}
        </Field>
        <Field label="Album">{row.album || "Not reported"}</Field>
        <Field label="Run date" mono>
          {runDateLabel(row.run_date)}
        </Field>
        <Field label="Stage">{stageDisplay.text}</Field>
        <Field label="Profile" mono>
          {meta.profile_id || "--"}
        </Field>
        <Field label="Updated">{updated.primary}</Field>
        <Field label="Pipeline">
          {local.total > 0 || video.source === "local"
            ? "Local output"
            : video.source === "api"
              ? "API values"
              : "Not reported"}
        </Field>
      </dl>

      <dl className="mt-3 grid grid-cols-3 gap-4 border-b border-border pb-3">
        <Field label="Music updated">
          {formatAbsoluteTime(meta.music_updated_at ?? meta.music_started_at) ?? "Not reported"}
        </Field>
        <Field label="Image updated">
          {formatAbsoluteTime(meta.image_updated_at ?? meta.image_started_at) ?? "Not reported"}
        </Field>
        <Field label="YouTube updated">
          {formatAbsoluteTime(meta.youtube_updated_at ?? meta.youtube_created_at) ?? "Not reported"}
        </Field>
      </dl>

      {failed ? (
        <div className="mt-3 rounded-control border border-danger/30 bg-danger-soft px-3 py-2">
          <p className="text-body text-danger">
            {note ?? `${failedStage ?? "A stage"} failed${meta.batch_id ? ` on ${meta.batch_id}` : ""}.`}
          </p>
          <div className="mt-2 flex flex-wrap items-center gap-2">
            <Button
              variant="secondary"
              onClick={() => setRetryOpen(true)}
              disabled={!retryable || retrying}
              title={retryReason ?? undefined}
              data-testid="progress-retry-stage"
            >
              <Icon name="fa-rotate-left" size={14} />
              {retrying ? "Retrying" : "Retry failed stage"}
            </Button>
            {retryReason ? <span className="text-caption text-text-secondary">{retryReason}</span> : null}
          </div>
          {retryResult ? (
            <p
              className={classNames(
                "mt-2 text-meta",
                retryResult.tone === "success" ? "text-success" : "text-danger",
              )}
              role="status"
            >
              {retryResult.text}
            </p>
          ) : null}
        </div>
      ) : null}

      <div className="mt-4">
        <h3 className="text-card font-semibold text-text-primary">Stage timeline</h3>
        <ol className="mt-2 space-y-2" data-testid="progress-timeline">
          {timeline.map((step) => (
            <li key={step.key} className="flex items-start justify-between gap-4">
              <StatusDot tone={TIMELINE_TONE[step.state]} label={step.label} />
              <span
                className={classNames(
                  "min-w-0 truncate text-right text-meta",
                  step.state === "unavailable" ? "text-text-muted" : "text-text-secondary",
                )}
                title={step.detail}
              >
                {step.detail}
              </span>
            </li>
          ))}
        </ol>
      </div>

      <div className="mt-4">
        <h3 className="text-card font-semibold text-text-primary">Paths</h3>
        {paths.length ? (
          <div className="mt-1">
            {paths.map((path) => (
              <PathRow
                key={`${path.label}-${path.value}`}
                label={path.label}
                value={path.value}
                kind={path.kind}
                onOpenFolder={onOpenFolder}
                onReveal={onReveal}
                onOpenExternal={onOpenExternal}
              />
            ))}
          </div>
        ) : (
          <p className="mt-1 text-body text-text-secondary">
            This run does not report a folder or file path.
          </p>
        )}
        {meta.run_dir ? (
          <p className="mt-2 text-caption text-text-muted">Music files live in the run folder.</p>
        ) : null}
      </div>

      {manualMode ? (
        <div className="mt-4 rounded-control border border-border bg-surface-2 p-3" data-testid="progress-manual">
          <div className="flex items-start justify-between gap-3">
            <div>
              <h3 className="text-card font-semibold text-text-primary">Manual asset recovery</h3>
              <p className="mt-0.5 text-meta text-text-secondary">
                Expected images: background-16x9, background-9x16, thumbnail-16x9, thumbnail-9x16.
              </p>
            </div>
            <Badge tone={inspection?.ready ? "success" : "warning"}>
              {inspection ? `${inspection.readyCount}/${inspection.total} ready` : "Not inspected"}
            </Badge>
          </div>

          <p className="mt-2 break-all font-mono text-meta text-text-secondary">
            {inspection?.runDir || meta.run_dir || "No run folder reported"}
          </p>

          {inspection ? (
            <ul className="mt-2 grid gap-1 sm:grid-cols-2">
              {inspection.files.map((file) => (
                <li key={file.key} className="flex items-center justify-between gap-2 text-meta">
                  <span className="flex min-w-0 items-center gap-2 text-text-secondary">
                    <Icon name="fa-image" size={13} className="shrink-0" />
                    <span className="truncate">{file.label}</span>
                  </span>
                  <Badge tone={file.present ? "success" : "danger"}>
                    {file.present ? "Present" : "Missing"}
                  </Badge>
                </li>
              ))}
            </ul>
          ) : (
            <p className="mt-2 text-meta text-text-muted">
              {inspecting ? "Inspecting the run folder…" : "Select Check files to inspect the run folder."}
            </p>
          )}

          {hint ? <p className="mt-2 text-meta text-warning">{hint}</p> : null}
          {inspection?.error ? (
            <p className="mt-2 text-meta text-danger">{inspection.error}</p>
          ) : null}

          <div className="mt-3 flex flex-wrap items-center gap-2">
            <Button
              variant="secondary"
              onClick={() => onInspect(row)}
              disabled={inspecting}
            >
              <Icon name="fa-rotate" size={14} />
              {inspecting ? "Checking" : "Check files"}
            </Button>
            <Button
              variant="secondary"
              onClick={() => onOpenFolder(meta.run_dir ?? "")}
              disabled={!meta.run_dir}
            >
              <Icon name="fa-folder-open" size={14} />
              Open folder
            </Button>
            <Button
              variant="primary"
              onClick={() => onSyncManual(row)}
              disabled={!inspection?.ready || syncing}
              title={
                !inspection?.ready
                  ? "Every expected image must be present before the pipeline can continue."
                  : undefined
              }
              data-testid="progress-continue-pipeline"
            >
              {syncing ? "Syncing" : "Continue pipeline"}
            </Button>
          </div>
        </div>
      ) : null}

      {video.source === "none" && local.total === 0 ? (
        <p className="mt-3 text-caption text-text-muted">
          Render and merge have no local output or API value for this run.
        </p>
      ) : null}

      {youtubePanel}

      <Dialog open={retryOpen} onOpenChange={setRetryOpen}>
        <DialogContent
          title="Retry image stage?"
          description={`This re-queues the failed image jobs for ${row.batch}. Generated files on disk are kept.`}
        >
          <div className="flex justify-end gap-2">
            <Button variant="secondary" onClick={() => setRetryOpen(false)}>
              Cancel
            </Button>
            <Button variant="primary" onClick={runRetry}>
              Retry image stage
            </Button>
          </div>
        </DialogContent>
      </Dialog>
    </Card>
  );
}
