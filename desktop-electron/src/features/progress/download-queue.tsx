import { FolderOpen, RotateCcw } from "lucide-react";
import { Button } from "../../components/button";
import { Card } from "../../components/card";
import { Badge } from "../../components/status";
import { TBody, TD, TH, THead, TR } from "../../components/table";
import type { DownloadQueueRow } from "./progress-format";

interface DownloadQueueProps {
  rows: DownloadQueueRow[];
  error: string | null;
  onReveal: (path: string) => void;
  onOpenFolder: (path: string) => void;
}

/** PG-39…PG-43: hidden when the server queue is empty. */
export function DownloadQueue({ rows, error, onReveal, onOpenFolder }: DownloadQueueProps) {
  if (rows.length === 0) return null;

  return (
    <Card className="overflow-hidden" data-testid="progress-download-card">
      <div className="flex items-start justify-between gap-4 border-b border-border px-4 py-3">
        <div>
          <h2 className="text-title font-semibold text-text-primary">Download queue</h2>
          <p className="mt-0.5 text-meta text-text-secondary">
            Pending MP3 downloads reported by the server. Retry arrives with the shell download
            coordinator in P4.
          </p>
        </div>
        <div className="flex items-center gap-2">
          {error ? <Badge tone="warning">Stale</Badge> : null}
          <span className="font-mono text-caption text-text-muted">{rows.length} pending</span>
        </div>
      </div>

      <div className="overflow-auto">
        <table className="w-full min-w-[900px] table-fixed border-collapse text-body">
          <colgroup>
            <col className="w-[220px]" />
            <col className="w-[160px]" />
            <col className="w-[270px]" />
            <col className="w-[96px]" />
            <col className="w-[140px]" />
            <col className="w-[200px]" />
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
                  {row.secondaryPath ? (
                    <p
                      className="mt-0.5 truncate font-mono text-caption text-text-muted"
                      title={row.secondaryPath}
                    >
                      {row.secondaryPath}
                    </p>
                  ) : null}
                </TD>
                <TD className="py-2 align-top">
                  <Badge tone={row.stateTone}>{row.state}</Badge>
                </TD>
                <TD className="py-2 align-top font-mono text-meta">{row.progress}</TD>
                <TD className="py-2 align-top">
                  <div className="flex items-center gap-1">
                    <Button
                      variant="ghost"
                      disabled
                      title={
                        row.hasDownloadUrl
                          ? "Download retry needs the shell download coordinator (P4)."
                          : "This task has no download URL."
                      }
                    >
                      <RotateCcw size={13} aria-hidden="true" />
                      Retry
                    </Button>
                    {row.revealPath ? (
                      <Button variant="ghost" onClick={() => onReveal(row.revealPath ?? "")}>
                        <FolderOpen size={13} aria-hidden="true" />
                        Reveal
                      </Button>
                    ) : row.folderPath ? (
                      <Button variant="ghost" onClick={() => onOpenFolder(row.folderPath ?? "")}>
                        <FolderOpen size={13} aria-hidden="true" />
                        Open folder
                      </Button>
                    ) : (
                      <Button variant="ghost" disabled title="No target folder is reported.">
                        <FolderOpen size={13} aria-hidden="true" />
                        Open folder
                      </Button>
                    )}
                  </div>
                </TD>
              </TR>
            ))}
          </TBody>
        </table>
      </div>

      {error ? <p className="border-t border-border px-4 py-2 text-caption text-warning">{error}</p> : null}
    </Card>
  );
}
