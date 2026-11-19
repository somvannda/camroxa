import { FolderOpen } from "lucide-react";
import { Card } from "../../../components/card";
import { Badge } from "../../../components/status";
import { Table, TBody, TD, TH, THead, TR } from "../../../components/table";
import { classNames, formatDateTime } from "../../../lib/format";
import { songFolder, type HistoryRow } from "../music-format";
import type { HistoryFilters } from "../music-types";
import { CheckField, DateField } from "./music-ui";

const COLUMNS = [
  "No",
  "Album",
  "Title",
  "Description",
  "Structure",
  "Primary",
  "Secondary",
  "Suno",
  "Generated",
];

function statusTone(status: string): "neutral" | "success" | "warning" | "danger" {
  const normalised = status.trim().toLowerCase();
  if (["completed", "ready", "downloaded", "done"].includes(normalised)) return "success";
  if (["failed", "error", "suno_failed"].includes(normalised)) return "danger";
  if (normalised.startsWith("pending") || normalised.includes("running")) return "warning";
  return "neutral";
}

function formatDateOnly(value: string | null | undefined): string {
  if (!value) return "--";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "--";
  return new Intl.DateTimeFormat("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
  }).format(date);
}

interface MusicHistoryCardProps {
  rows: HistoryRow[];
  summary: string;
  updatedAt: string;
  filters: HistoryFilters;
  loading: boolean;
  selectedKey: string | null;
  onFiltersChange: (patch: Partial<HistoryFilters>) => void;
  onSelectRow: (row: HistoryRow) => void;
  onOpenFolder: (row: HistoryRow, side: "primary" | "secondary") => void;
}

function FolderButton({
  path,
  label,
  onClick,
}: {
  path: string;
  label: string;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      className="ml-1 inline-flex h-7 w-7 shrink-0 items-center justify-center rounded-[6px] text-text-muted hover:bg-surface-hover hover:text-text-primary disabled:opacity-40"
      aria-label={path ? `${label} folder` : `${label} folder missing`}
      title={path || "No folder path"}
      disabled={!path}
      onClick={(event) => {
        event.stopPropagation();
        onClick();
      }}
    >
      <FolderOpen size={14} strokeWidth={1.5} />
    </button>
  );
}

export function MusicHistoryCard({
  rows,
  summary,
  updatedAt,
  filters,
  loading,
  selectedKey,
  onFiltersChange,
  onSelectRow,
  onOpenFolder,
}: MusicHistoryCardProps) {
  return (
    <Card className="p-4" data-testid="history-card">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h2 className="text-title font-semibold text-text-primary">History</h2>
          <p className="mt-0.5 text-meta text-text-secondary">
            Latest batch history. A row loads its title, album, lyrics and prompt ids into the
            composer.
          </p>
        </div>
        <div className="text-right">
          <p className="text-meta text-text-secondary" data-testid="history-summary">
            {summary || "No history loaded yet."}
          </p>
          <p className="text-caption text-text-muted">Updated {formatDateTime(updatedAt)}</p>
        </div>
      </div>

      <div className="mt-3 flex flex-wrap items-end gap-3">
        <div className="w-[160px]">
          <DateField
            id="history-from"
            label="From"
            value={filters.fromDate}
            onChange={(value) => onFiltersChange({ fromDate: value })}
            testId="history-from"
          />
        </div>
        <div className="w-[160px]">
          <DateField
            id="history-to"
            label="To"
            value={filters.toDate}
            onChange={(value) => onFiltersChange({ toDate: value })}
            testId="history-to"
          />
        </div>
        <div className="flex items-end pb-1">
          <CheckField
            id="history-last-batch"
            label="Last batch only"
            checked={filters.lastBatchOnly}
            onChange={(checked) => onFiltersChange({ lastBatchOnly: checked })}
            testId="history-last-batch"
          />
        </div>
      </div>

      <div className="mt-3">
        <Table className="[&_td]:px-2 [&_th]:px-2">
          <THead>
            <TR className="hover:bg-surface-2">
              {COLUMNS.map((column) => (
                <TH key={column}>{column}</TH>
              ))}
            </TR>
          </THead>
          <TBody>
            {loading ? (
              <TR className="hover:bg-transparent">
                <TD colSpan={COLUMNS.length} className="text-text-secondary">
                  Loading history...
                </TD>
              </TR>
            ) : rows.length === 0 ? (
              <TR className="hover:bg-transparent">
                <TD colSpan={COLUMNS.length} className="text-text-secondary" data-testid="history-empty">
                  No history rows match the current filters.
                </TD>
              </TR>
            ) : (
              rows.map((row) => {
                const suno = row.song.suno_status || row.song.status || "--";
                const selected = selectedKey === row.key;
                return (
                  <TR
                    key={row.key}
                    tabIndex={0}
                    aria-selected={selected}
                    className={classNames(
                      "cursor-pointer",
                      selected && "bg-accent-soft",
                    )}
                    onClick={() => onSelectRow(row)}
                    onKeyDown={(event) => {
                      if (event.key === "Enter" || event.key === " ") {
                        event.preventDefault();
                        onSelectRow(row);
                      }
                    }}
                    data-testid={`history-row-${row.song.song_id}`}
                  >
                    <TD className="text-text-muted text-tabular">{row.rowNumber}</TD>
                    <TD className="max-w-[150px] truncate text-text-secondary">
                      {row.song.album || row.batch.ok_album || "--"}
                    </TD>
                    <TD className="max-w-[200px]">
                      <span className="block truncate font-medium text-text-primary">
                        {row.song.title || "--"}
                      </span>
                      <span className="block truncate text-caption text-text-muted">
                        Batch {row.batchIndex + 1} · {row.batch.batch_id.slice(0, 8)}
                      </span>
                    </TD>
                    <TD className="max-w-[140px] truncate text-text-secondary">
                      {row.song.description_name || "--"}
                    </TD>
                    <TD className="max-w-[140px] truncate text-text-secondary">
                      {row.song.structure_name || "--"}
                    </TD>
                    <TD className="text-text-secondary">
                      <span className="inline-flex max-w-[130px] items-center">
                        <span className="truncate">{row.batch.ok_profile_name || "--"}</span>
                        <FolderButton
                          path={songFolder(row.song, "primary")}
                          label="Primary"
                          onClick={() => onOpenFolder(row, "primary")}
                        />
                      </span>
                    </TD>
                    <TD className="text-text-secondary">
                      <span className="inline-flex max-w-[130px] items-center">
                        <span className="truncate">{row.batch.alt_profile_name || "--"}</span>
                        <FolderButton
                          path={songFolder(row.song, "secondary")}
                          label="Secondary"
                          onClick={() => onOpenFolder(row, "secondary")}
                        />
                      </span>
                    </TD>
                    <TD>
                      <Badge tone={statusTone(suno)}>{suno.replace(/_/g, " ")}</Badge>
                    </TD>
                    <TD
                      className="text-text-muted text-tabular"
                      title={row.song.created_at ? formatDateTime(row.song.created_at) : undefined}
                    >
                      {formatDateOnly(row.song.created_at)}
                    </TD>
                  </TR>
                );
              })
            )}
          </TBody>
        </Table>
      </div>
    </Card>
  );
}
