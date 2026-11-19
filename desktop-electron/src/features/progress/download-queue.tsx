import { Icon } from "../../components/icon";
import { Button } from "../../components/button";
import { Card } from "../../components/card";
import { Badge } from "../../components/status";
import { TBody, TD, TH, THead, TR } from "../../components/table";
import type { DownloadQueueRow } from "./progress-format";

interface DownloadQueueProps {
  rows: DownloadQueueRow[];
  error: string | null;
  paused: boolean;
  active: number;
  concurrency: number;
  root: string | null;
  busy: boolean;
  onRetry: (key: string) => void;
  onCancel: (key: string) => void;
  onReveal: (key: string) => void;
  onOpenFolder: (path: string) => void;
  onTogglePause: (paused: boolean) => void;
}

/**
 * PG-39…PG-43: hidden when the coordinator tracks nothing.
 *
 * Every action maps to a real IPC call. Retry stays disabled only when the row
 * cannot be retried, and the title says why.
 */
export function DownloadQueue({
  rows,
  error,
  paused,
  active,
  concurrency,
  root,
  busy,
  onRetry,
  onCancel,
  onReveal,
  onOpenFolder,
  onTogglePause,
}: DownloadQueueProps) {
  if (rows.length === 0) return null;

  return (
    <Card className="overflow-hidden" data-testid="progress-download-card">
      <div className="flex flex-wrap items-start justify-between gap-4 border-b border-border px-4 py-3">
        <div>
          <h2 className="text-title font-semibold text-text-primary">Download queue</h2>
          <p className="mt-0.5 text-meta text-text-secondary" data-testid="progress-download-summary">
            {paused
              ? "Downloads are paused. Resume to keep saving Suno songs."
              : "Suno songs are saved by the desktop app in the background."}{" "}
            {root ? (
              <>
                Saving to <span className="font-mono">{root}</span>.
              </>
            ) : null}
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          {error ? <Badge tone="warning">Stale</Badge> : null}
          {active > 0 ? (
            <Badge tone="accent">
              {active} of {concurrency} downloading
            </Badge>
          ) : null}
          <span className="font-mono text-caption text-text-muted">
            {rows.length} item{rows.length === 1 ? "" : "s"}
          </span>
          <Button
            variant="ghost"
            className="h-7 px-2.5"
            data-testid="progress-download-pause"
            disabled={busy}
            title={paused ? "Resume automatic downloads." : "Pause automatic downloads."}
            onClick={() => onTogglePause(!paused)}
          >
            <Icon name={paused ? "fa-play" : "fa-pause"} size={13} />
            {paused ? "Resume" : "Pause"}
          </Button>
        </div>
      </div>

      <div className="overflow-auto">
        <table className="w-full min-w-[1020px] table-fixed border-collapse text-body">
          <colgroup>
            <col className="w-[190px]" />
            <col className="w-[120px]" />
            <col className="w-[246px]" />
            <col className="w-[104px]" />
            <col className="w-[164px]" />
            <col className="w-[224px]" />
          </colgroup>
          <THead>
            <TR className="hover:bg-transparent">
              <TH>Song</TH>
              <TH>Channel</TH>
              <TH>Target path</TH>
              <TH>State</TH>
              <TH>Progress</TH>
              <TH>Actions</TH>
            </TR>
          </THead>
          <TBody>
            {rows.map((row) => (
              <TR key={row.key} data-testid="progress-download-row" className="align-top">
                <TD className="py-2 align-top">
                  <span className="block truncate">{row.song}</span>
                  {row.subtitle ? (
                    <p className="mt-0.5 truncate text-caption text-text-muted">{row.subtitle}</p>
                  ) : null}
                </TD>
                <TD className="py-2 align-top">
                  <span className="block truncate">{row.channel}</span>
                </TD>
                <TD className="py-2 align-top">
                  <span className="block truncate font-mono text-meta" title={row.path}>
                    {row.path}
                  </span>
                </TD>
                <TD className="py-2 align-top">
                  <Badge tone={row.stateTone}>{row.state}</Badge>
                </TD>
                <TD className="py-2 align-top font-mono text-meta">
                  <span className="text-tabular">{row.progress}</span>
                  {row.error ? (
                    <p className="mt-0.5 whitespace-normal break-words font-sans text-caption text-danger" role="status">
                      {row.error}
                    </p>
                  ) : null}
                </TD>
                <TD className="py-2 align-top">
                  <div className="flex flex-wrap items-center gap-1">
                    {row.showRetry ? (
                      <Button
                        variant="ghost"
                        className="h-7 px-2"
                        disabled={!row.canRetry || busy}
                        title={
                          row.canRetry
                            ? "Retry this download."
                            : "This task has no download URL."
                        }
                        onClick={() => onRetry(row.key)}
                      >
                        <Icon name="fa-rotate-left" size={13} />
                        Retry
                      </Button>
                    ) : null}
                    {row.canCancel ? (
                      <Button
                        variant="ghost"
                        className="h-7 px-2"
                        disabled={busy}
                        title="Cancel this download and delete the partial file."
                        onClick={() => onCancel(row.key)}
                      >
                        <Icon name="fa-xmark" size={13} />
                        Cancel
                      </Button>
                    ) : null}
                    {row.canReveal ? (
                      <Button
                        variant="ghost"
                        className="h-7 w-7 px-0"
                        disabled={busy}
                        aria-label="Reveal"
                        title="Reveal the downloaded file."
                        onClick={() => onReveal(row.key)}
                      >
                        <Icon name="fa-folder-open" size={14} />
                      </Button>
                    ) : row.folderPath ? (
                      <Button
                        variant="ghost"
                        className="h-7 w-7 px-0"
                        disabled={busy}
                        aria-label="Open folder"
                        title="Open the target folder."
                        onClick={() => onOpenFolder(row.folderPath ?? "")}
                      >
                        <Icon name="fa-folder-open" size={14} />
                      </Button>
                    ) : (
                      <Button
                        variant="ghost"
                        className="h-7 w-7 px-0"
                        disabled
                        aria-label="Open folder"
                        title="No target folder is reported for this task."
                      >
                        <Icon name="fa-folder-open" size={14} />
                      </Button>
                    )}
                  </div>
                </TD>
              </TR>
            ))}
          </TBody>
        </table>
      </div>

      {error ? (
        <p className="border-t border-border px-4 py-2 text-caption text-warning">
          {error} The last download state is still shown.
        </p>
      ) : null}
    </Card>
  );
}
