import { Button } from "../../components/button";
import { Icon } from "../../components/icon";
import type {
  VizzyExportProgress,
  VizzyExportResult,
} from "../../../electron/shared/types";
import { formatBytes, formatDuration } from "./vizzy-format";

export interface VizzyExportStatusProps {
  running: boolean;
  progress: VizzyExportProgress | null;
  result: VizzyExportResult | null;
  error: string | null;
  onCancel: () => void;
  onDismiss: () => void;
  onReveal: (name: string) => void;
  onOpenRenders: () => void;
}

/** One-row export status under the strip: progress, cancel, or the last result. */
export function VizzyExportStatus({
  running,
  progress,
  result,
  error,
  onCancel,
  onDismiss,
  onReveal,
  onOpenRenders,
}: VizzyExportStatusProps) {
  if (!running && !result && !error) return null;

  if (running) {
    const percent = progress?.percent ?? 0;
    return (
      <div
        className="flex h-9 shrink-0 items-center gap-3 border-b border-border bg-surface-1 px-4"
        data-testid="vizzy-export-status"
      >
        <span className="h-3 w-3 animate-spin rounded-full border border-accent border-t-transparent" />
        <span className="text-body-sm text-text-primary">Exporting</span>
        <div className="h-1.5 w-40 overflow-hidden rounded-full bg-surface-3">
          <div
            className="h-full rounded-full bg-accent transition-[width] duration-300"
            style={{ width: `${percent}%` }}
          />
        </div>
        <span className="font-mono text-meta text-text-muted">{percent}%</span>
        <span className="min-w-0 truncate text-meta text-text-muted">
          {progress ? `${progress.stage} · ${progress.done}/${progress.total} frames` : "Preparing"}
        </span>
        <Button
          variant="ghost"
          className="ml-auto"
          onClick={onCancel}
          data-testid="vizzy-export-status-cancel"
        >
          Cancel
        </Button>
      </div>
    );
  }

  if (result) {
    return (
      <div
        className="flex h-9 shrink-0 items-center gap-2 border-b border-success/30 bg-success-soft px-4"
        data-testid="vizzy-export-status"
      >
        <Icon name="fa-circle-check" size={12} className="text-success" />
        <span className="max-w-[300px] truncate text-body-sm text-text-primary">{result.name}</span>
        <span className="text-meta text-text-muted">
          {formatBytes(result.bytes)} · {formatDuration(result.durationSec)} ·{" "}
          {result.width}×{result.height}
          {result.videoCodec ? ` · ${result.videoCodec}` : ""}
        </span>
        <div className="ml-auto flex items-center gap-1">
          <Button variant="secondary" onClick={() => onReveal(result.name)}>
            Show file
          </Button>
          <Button variant="ghost" onClick={onOpenRenders}>
            Renders
          </Button>
          <Button variant="ghost" onClick={onDismiss} aria-label="Dismiss export result">
            <Icon name="fa-xmark" size={13} />
          </Button>
        </div>
      </div>
    );
  }

  return (
    <div
      className="flex h-9 shrink-0 items-center gap-2 border-b border-danger/30 bg-danger-soft px-4"
      role="alert"
      data-testid="vizzy-export-status"
    >
      <Icon name="fa-triangle-exclamation" size={12} className="text-danger" />
      <span className="min-w-0 flex-1 truncate text-body-sm text-text-primary">{error}</span>
      <Button variant="ghost" onClick={onDismiss} aria-label="Dismiss export error">
        <Icon name="fa-xmark" size={13} />
      </Button>
    </div>
  );
}
