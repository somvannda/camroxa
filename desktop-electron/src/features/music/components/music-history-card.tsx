import { useMemo } from "react";
import { Icon } from "../../../components/icon";
import { Card } from "../../../components/card";
import { Badge } from "../../../components/status";
import { Table, TBody, TD, TH, THead, TR } from "../../../components/table";
import { classNames, formatDateTime } from "../../../lib/format";
import { songFolder, type HistoryRow } from "../music-format";
import type { HistoryFilters, MusicHistoryBatch, MusicHistorySong } from "../music-types";
import { CheckField, DateField } from "./music-ui";

const COLUMNS = [
  "No",
  "Album 1",
  "Album 2",
  "Title",
  "Description",
  "Structure",
  "Mood",
  "Primary Channel",
  "Secondary Channel",
  "Suno",
  "Run date",
];

const FAILURE_STATUSES = new Set([
  "failed",
  "error",
  "suno_failed",
  "draft_failed",
  "rejected",
  "sensitive_word_error",
  "sensitive_content",
  "content_policy",
  "policy_violation",
  "create_task_failed",
  "generate_audio_failed",
  "generate_lyrics_failed",
  "callback_exception",
  "failure",
  "cancelled",
  "canceled",
]);
const SUCCESS_STATUSES = new Set(["success", "complete", "completed", "done", "suno_success"]);
const PENDING_STATUSES = new Set([
  "",
  "pending",
  "queued",
  "running",
  "processing",
  "in_progress",
  "drafting",
  "draft_ready",
  "text_success",
  "first_success",
]);
const STATUS_LABELS: Record<string, string> = {
  pending: "Pending",
  drafting: "Drafting",
  draft_ready: "Draft ready",
  draft_failed: "Draft failed",
  suno_failed: "Failed",
  suno_success: "Success",
  completed: "Completed",
  complete: "Complete",
};

function normalizeStatus(value: string | null | undefined): string {
  return String(value ?? "")
    .trim()
    .toLowerCase();
}

function titleCase(value: string): string {
  return value
    .replace(/_/g, " ")
    .trim()
    .replace(/\b\w/g, (letter) => letter.toUpperCase());
}

function shortReason(value: string | null | undefined): string {
  const text = String(value ?? "")
    .replace(/\s+/g, " ")
    .trim();
  if (!text) return "";
  return text.length > 80 ? `${text.slice(0, 77)}…` : text;
}

function sunoLabel(song: MusicHistorySong): string {
  const songStatus = normalizeStatus(song.status);
  const providerStatus = normalizeStatus(song.suno_status);
  if (FAILURE_STATUSES.has(songStatus) || FAILURE_STATUSES.has(providerStatus)) {
    const reason = shortReason(song.suno_error_message);
    if (reason) return `Failed (Reason: ${reason})`;
    if (providerStatus && !FAILURE_STATUSES.has(providerStatus)) {
      return `Failed (Reason: ${providerStatus.replace(/_/g, " ")})`;
    }
    return "Failed";
  }
  for (const candidate of [providerStatus, songStatus]) {
    if (SUCCESS_STATUSES.has(candidate)) return STATUS_LABELS[candidate] ?? titleCase(candidate);
  }
  for (const candidate of [providerStatus, songStatus]) {
    if (PENDING_STATUSES.has(candidate)) return STATUS_LABELS[candidate] ?? titleCase(candidate);
  }
  const fallback = song.suno_status || song.status || "pending";
  return STATUS_LABELS[normalizeStatus(fallback)] ?? titleCase(fallback);
}

function statusTone(status: string): "neutral" | "success" | "warning" | "danger" {
  const normalised = status.trim().toLowerCase();
  if (normalised.startsWith("failed")) return "danger";
  if (["completed", "ready", "downloaded", "done", "success"].includes(normalised)) return "success";
  if (["failed", "error", "suno_failed"].includes(normalised)) return "danger";
  if (["pending", "queued", "running", "drafting", "draft ready"].includes(normalised)) {
    return "warning";
  }
  return "neutral";
}

function formatDateOnly(value: string | null | undefined): string {
  if (!value) return "--";
  const date = new Date(`${value}T00:00:00`);
  if (Number.isNaN(date.getTime())) return "--";
  return new Intl.DateTimeFormat("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
  }).format(date);
}

function titleGenerating(song: MusicHistorySong): boolean {
  if (String(song.title ?? "").trim()) return false;
  return ["pending", "processing", "drafting"].includes(normalizeStatus(song.status || "pending"));
}

function batchSeparatorLabel(batch: MusicHistoryBatch): string {
  const runDate = formatDateOnly(batch.from_date || batch.to_date);
  const generated = formatDateTime(batch.created_at || batch.updated_at);
  const okName = batch.ok_profile_name || "Primary";
  const altName = batch.alt_profile_name || "Secondary";
  const album1 = String(batch.ok_album ?? "").trim();
  const album2 = String(batch.alt_album ?? "").trim();
  const albumBits = [
    album1 ? `album 1 ${album1}` : "",
    album2 ? `album 2 ${album2}` : "",
  ].filter(Boolean);
  const albumPart = albumBits.length ? `${albumBits.join(" · ")} · ` : "";
  const songCount = Number(batch.song_count ?? batch.songs?.length ?? 0);
  return `Batch ${batch.batch_id.slice(0, 8)} · ${okName} → ${altName} · ${albumPart}${songCount} ${
    songCount === 1 ? "song" : "songs"
  } · Run ${runDate} · Generated ${generated}`;
}

type DisplayRow =
  | { kind: "batch"; key: string; batch: MusicHistoryBatch }
  | { kind: "song"; key: string; row: HistoryRow };

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
      <Icon name="fa-folder-open" size={14} />
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
  const displayRows = useMemo<DisplayRow[]>(() => {
    const out: DisplayRow[] = [];
    let lastBatchId = "";
    rows.forEach((row) => {
      if (row.batch.batch_id !== lastBatchId) {
        lastBatchId = row.batch.batch_id;
        out.push({ kind: "batch", key: `batch-${row.batch.batch_id}`, batch: row.batch });
      }
      out.push({ kind: "song", key: row.key, row });
    });
    return out;
  }, [rows]);

  return (
    <Card className="p-4" data-testid="history-card">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h2 className="text-title font-semibold text-text-primary">History</h2>
          <p className="mt-0.5 text-meta text-text-secondary">
            Batch history in run order. A row loads its title, album, lyrics and prompt ids into
            the composer.
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
                <TH key={column} className="whitespace-nowrap">
                  {column}
                </TH>
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
            ) : displayRows.length === 0 ? (
              <TR className="hover:bg-transparent">
                <TD colSpan={COLUMNS.length} className="text-text-secondary" data-testid="history-empty">
                  No history rows match the current filters.
                </TD>
              </TR>
            ) : (
              displayRows.map((entry) => {
                if (entry.kind === "batch") {
                  return (
                    <TR
                      key={entry.key}
                      className="hover:bg-transparent"
                      data-testid={`history-batch-${entry.batch.batch_id}`}
                    >
                      <TD
                        colSpan={COLUMNS.length}
                        className="bg-accent-soft py-1.5 text-caption font-medium text-accent"
                      >
                        {batchSeparatorLabel(entry.batch)}
                      </TD>
                    </TR>
                  );
                }
                const { row } = entry;
                const suno = sunoLabel(row.song);
                const selected = selectedKey === row.key;
                return (
                  <TR
                    key={entry.key}
                    tabIndex={0}
                    aria-selected={selected}
                    className={classNames("cursor-pointer", selected && "bg-accent-soft")}
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
                    <TD className="max-w-[140px] truncate text-text-secondary">
                      {row.batch.ok_album || row.song.album || "—"}
                    </TD>
                    <TD className="max-w-[140px] truncate text-text-secondary">
                      {row.batch.alt_album || "—"}
                    </TD>
                    <TD className="max-w-[200px]">
                      {titleGenerating(row.song) ? (
                        <span className="text-caption text-text-muted">Generating…</span>
                      ) : (
                        <span
                          className="block truncate font-medium text-text-primary"
                          title={row.song.title ?? undefined}
                        >
                          {row.song.title || "—"}
                        </span>
                      )}
                    </TD>
                    <TD className="max-w-[140px] truncate text-text-secondary">
                      {row.song.description_name || "—"}
                    </TD>
                    <TD className="max-w-[140px] truncate text-text-secondary">
                      {row.song.structure_name || "—"}
                    </TD>
                    <TD className="max-w-[120px] truncate text-text-secondary">
                      {row.song.mood_name || "—"}
                    </TD>
                    <TD className="text-text-secondary">
                      <span className="inline-flex max-w-[150px] items-center">
                        <span className="truncate">{row.batch.ok_profile_name || "—"}</span>
                        <FolderButton
                          path={songFolder(row.song, "primary")}
                          label="Primary"
                          onClick={() => onOpenFolder(row, "primary")}
                        />
                      </span>
                    </TD>
                    <TD className="text-text-secondary">
                      <span className="inline-flex max-w-[150px] items-center">
                        <span className="truncate">{row.batch.alt_profile_name || "—"}</span>
                        <FolderButton
                          path={songFolder(row.song, "secondary")}
                          label="Secondary"
                          onClick={() => onOpenFolder(row, "secondary")}
                        />
                      </span>
                    </TD>
                    <TD>
                      <Badge tone={statusTone(suno)}>
                        <span
                          className="block max-w-[150px] truncate"
                          title={row.song.suno_error_message || suno}
                        >
                          {suno}
                        </span>
                      </Badge>
                    </TD>
                    <TD
                      className="whitespace-nowrap text-text-muted text-tabular"
                      title={row.song.created_at ? formatDateTime(row.song.created_at) : undefined}
                    >
                      {formatDateOnly(row.batch.from_date || row.batch.to_date)}
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
