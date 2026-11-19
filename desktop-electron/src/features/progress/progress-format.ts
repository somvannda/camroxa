import { formatCount } from "../../lib/format";
import type { DownloadItemInfo, DownloadItemState } from "../../../electron/shared/types";
import type { ProgressListResponse, ProgressRow } from "./progress-types";

export const PROGRESS_POLL_MS = 12_000;
export const PROGRESS_ACTIVE_POLL_MS = 4_000;
export const DOWNLOADS_POLL_MS = 5_000;
export const API_ROW_CAP = 100;

export const LIMIT_OPTIONS = [25, 50, 100, 200] as const;
export const DEFAULT_LIMIT = 50;

export const STAGE_FILTERS = [
  { value: "all", label: "All stages" },
  { value: "music", label: "Music" },
  { value: "image", label: "Image" },
  { value: "converter", label: "Converter" },
  { value: "merger", label: "Merge" },
  { value: "youtube", label: "YouTube" },
  { value: "done", label: "Done" },
  { value: "error", label: "Error" },
] as const;

export type StageFilter = (typeof STAGE_FILTERS)[number]["value"];
export type ProgressTone = "neutral" | "success" | "warning" | "danger" | "accent";

export const PIPELINE_MISSING = "No pipeline stage reported";

const ACTIVE_HIDDEN_STAGES = new Set(["done", "completed"]);
const CONVERTER_STAGES = new Set(["converter", "export"]);
const MERGER_STAGES = new Set(["merger", "merge"]);

export function todayYmd(now: Date = new Date()): string {
  const year = now.getFullYear();
  const month = String(now.getMonth() + 1).padStart(2, "0");
  const day = String(now.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
}

/** The date-range rule is PG-07: To must not be before From. */
export function rangeError(from: string, to: string): string | null {
  if (!from || !to) return "Choose both a From and a To date.";
  if (to < from) return "The To date must be on or after the From date.";
  return null;
}

export interface ProgressQuery {
  [key: string]: string | number | boolean;
  limit: number;
  active_only: boolean;
  from_date: string;
  to_date: string;
}

/**
 * The API caps `limit` at 100, so a 200-row display still requests 100.
 * Active/Stage filtering happens on the client, after the local overlay.
 */
export function progressQuery(
  from: string,
  to: string,
  limit: number,
  activeOnly: boolean,
): ProgressQuery {
  return {
    limit: Math.min(API_ROW_CAP, Math.max(1, Math.trunc(limit))),
    active_only: activeOnly,
    from_date: from,
    to_date: to,
  };
}

export function rowKey(row: ProgressRow): string {
  const meta = row.meta;
  return `${row.batch}|${row.run_date}|${meta.profile_id}|${meta.role}`;
}

function rowTimestamp(row: ProgressRow): number {
  const value = row.meta.updated_at;
  const parsed = value ? Date.parse(value) : Number.NaN;
  return Number.isNaN(parsed) ? 0 : parsed;
}

/** PG-15: batch + run date identify a row; duplicates collapse and newest sort first. */
export function prepareRows(rows: ProgressRow[]): ProgressRow[] {
  const seen = new Set<string>();
  const unique: ProgressRow[] = [];
  for (const row of rows) {
    const key = rowKey(row);
    if (seen.has(key)) continue;
    seen.add(key);
    unique.push(row);
  }
  return unique.sort((left, right) => {
    if (left.run_date !== right.run_date) return right.run_date.localeCompare(left.run_date);
    return rowTimestamp(right) - rowTimestamp(left);
  });
}

export function stageKey(stage: string): string {
  const value = String(stage ?? "").trim().toLowerCase();
  if (value === "export") return "converter";
  if (value === "merge") return "merger";
  return value;
}

export function stageLabel(stage: string): string {
  const value = String(stage ?? "").trim();
  const key = stageKey(value);
  switch (key) {
    case "":
      return "Not reported";
    case "converter":
      return "Converter";
    case "merger":
      return "Merge";
    case "music":
      return "Music";
    case "image":
      return "Image";
    case "youtube":
      return "YouTube";
    case "done":
    case "completed":
      return "Done";
    case "error":
    case "failed":
      return "Error";
    default:
      return value.charAt(0).toUpperCase() + value.slice(1);
  }
}

export function stageBadgeTone(stage: string): ProgressTone {
  const key = stageKey(stage);
  if (key === "done" || key === "completed") return "success";
  if (key === "error" || key === "failed") return "danger";
  if (key === "youtube") return "accent";
  return "neutral";
}

export function normalizeStatus(status: string): string {
  const key = String(status ?? "").trim().toLowerCase();
  if (key === "done" || key === "success") return "completed";
  return key;
}

export function statusLabel(status: string): string {
  const value = String(status ?? "").trim();
  if (!value) return "Not reported";
  const key = value.toLowerCase();
  if (key === "success" || key === "done") return "Completed";
  return value.charAt(0).toUpperCase() + value.slice(1);
}

export function statusBadgeTone(status: string): ProgressTone {
  const key = normalizeStatus(status);
  if (["failed", "blocked", "error"].some((token) => key.includes(token))) return "danger";
  if (["completed", "ready", "published", "uploaded"].some((token) => key.includes(token))) {
    return "success";
  }
  if (["pending", "queued", "waiting", "preparing"].some((token) => key.includes(token))) {
    return "warning";
  }
  if (
    ["running", "rendering", "generating", "downloading", "converting", "merging", "uploading", "progress"].some(
      (token) => key.includes(token),
    )
  ) {
    return "accent";
  }
  return "neutral";
}

function hasReelBranch(row: ProgressRow): boolean {
  const meta = row.meta;
  if (meta.reel_ready) return true;
  if (meta.background_9x16_path || meta.thumbnail_9x16_path) return true;
  const text = `${row.converter ?? ""} ${row.merge ?? ""}`.toLowerCase();
  if (["reel missing", "reel n/a", "reel not applicable", "reel not required"].some((token) => text.includes(token))) {
    return false;
  }
  const count = /reel\s+(\d+)\s*\/\s*(\d+)/.exec(text);
  if (count && Number(count[1]) > 0) return true;
  return ["reel merged", "reel single", "reel completed", "reel pending", "exporting reel", "merging reel"].some(
    (token) => text.includes(token),
  );
}

/** PG-03: hide finished runs, keep YouTube, errors and waiting rows visible. */
export function isActiveRow(row: ProgressRow): boolean {
  const key = stageKey(row.stage);
  if (ACTIVE_HIDDEN_STAGES.has(key)) return false;
  if (row.meta.pipeline_complete) return false;
  const merge = String(row.merge ?? "").toLowerCase();
  const longDone = merge.includes("long completed") || merge.includes("long merged");
  const reelDone = merge.includes("reel completed") || merge.includes("reel merged");
  if (longDone && (reelDone || !hasReelBranch(row))) return false;
  return true;
}

export function matchesStageFilter(stage: string, filter: StageFilter): boolean {
  if (filter === "all") return true;
  const key = stageKey(stage);
  if (filter === "converter") return CONVERTER_STAGES.has(key) || key === "converter";
  if (filter === "merger") return MERGER_STAGES.has(key) || key === "merger";
  return key === filter;
}

export interface FilterOptions {
  activeOnly: boolean;
  stage: StageFilter;
  limit?: number | null;
}

export function filterProgressRows(rows: ProgressRow[], options: FilterOptions): ProgressRow[] {
  let filtered = rows;
  if (options.activeOnly) filtered = filtered.filter(isActiveRow);
  if (options.stage !== "all") {
    filtered = filtered.filter((row) => matchesStageFilter(row.stage, options.stage));
  }
  if (options.limit != null) return filtered.slice(0, Math.max(0, options.limit));
  return filtered;
}

export interface ProgressStats {
  active: number;
  video: number;
  waiting: number;
  failed: number;
}

export function countStats(
  rows: ProgressRow[],
  manualMode: boolean,
  waitingKeys: ReadonlySet<string>,
): ProgressStats {
  let active = 0;
  let video = 0;
  let waiting = 0;
  let failed = 0;
  for (const row of rows) {
    const key = stageKey(row.stage);
    if (key !== "done" && key !== "completed" && key !== "error") active += 1;
    if (key === "converter" || key === "merger") video += 1;
    if (key === "image" && manualMode && waitingKeys.has(rowKey(row))) waiting += 1;
    const status = normalizeStatus(row.status);
    if (key === "error" || status === "failed" || status === "blocked") failed += 1;
  }
  return { active, video, waiting, failed };
}

export function summaryText(data: ProgressListResponse | null, rows: ProgressRow[]): string {
  if (!data) return "Loading progress rows.";
  const raw = String(data.summary ?? "").trim() || "Progress rows loaded";
  const base = /[.!?]$/.test(raw) ? raw : `${raw}.`;
  if (rows.length === 0) return base;
  const local = rows.filter(
    (row) => row.meta.long_ready || row.meta.reel_ready || row.meta.pipeline_complete,
  ).length;
  const suffix =
    local > 0
      ? `${local} run${local === 1 ? "" : "s"} report local video output.`
      : `${PIPELINE_MISSING}.`;
  return `${base} ${suffix}`;
}

export function metaLine(
  visible: number,
  loaded: number,
  downloads: number | null,
  stage: StageFilter,
  limit: number,
): string {
  const stageText = STAGE_FILTERS.find((item) => item.value === stage)?.label ?? "All stages";
  const count = downloads == null ? "--" : formatCount(downloads);
  const parts = [
    `${formatCount(visible)} visible row${visible === 1 ? "" : "s"}`,
    `${formatCount(loaded)} loaded`,
  ];
  if (limit > API_ROW_CAP && loaded <= API_ROW_CAP) {
    parts.push(`API cap ${API_ROW_CAP}`);
  }
  parts.push(`${count} download${downloads === 1 ? "" : "s"}`);
  parts.push(stageText);
  return parts.join(" · ");
}

function meaningful(value: unknown): string | null {
  const text = String(value ?? "").trim();
  if (!text || text === "-" || text === "—") return null;
  if (text.toLowerCase().startsWith("pending api parity")) return null;
  return text;
}

export interface LocalVideoState {
  converter: string | null;
  merge: string | null;
  source: "local" | "api" | "none";
}

/**
 * PG-18/PG-19: local runtime truth wins over the API text. Without local
 * output (and without a meaningful API value) the cell stays honest and points
 * at the Vizzy pipeline integration.
 */
export function localVideoState(row: ProgressRow): LocalVideoState {
  const meta = row.meta;
  const hasLong = Boolean(meta.long_ready);
  const hasReel = Boolean(meta.reel_ready);
  const complete = Boolean(meta.pipeline_complete);

  let converter: string | null = null;
  let merge: string | null = null;
  if (complete) {
    converter = "Completed";
    merge = "Completed";
  } else if (hasLong || hasReel) {
    converter = hasLong && hasReel ? "Long + reel ready" : hasLong ? "Long ready" : "Reel ready";
    merge = hasLong && hasReel ? "Completed" : hasLong ? "Long completed" : "Reel completed";
  }

  if (converter || merge) return { converter, merge, source: "local" };

  const apiConverter = meaningful(row.converter);
  const apiMerge = meaningful(row.merge);
  if (apiConverter || apiMerge) {
    return { converter: apiConverter, merge: apiMerge, source: "api" };
  }
  return { converter: null, merge: null, source: "none" };
}

export interface CellText {
  primary: string;
  secondary: string | null;
  title?: string;
}

export function runDateLabel(runDate: string): string {
  const text = String(runDate ?? "").trim();
  if (!text) return "Not reported";
  return text.includes("T") ? text.split("T")[0] : text;
}

export function channelRoleLabel(role: string): string {
  const value = String(role ?? "").trim();
  if (!value) return "Run";
  const upper = value.toUpperCase();
  if (upper === "OK") return "OK";
  if (upper === "ALT") return "ALT";
  return value;
}

export function channelCellText(row: ProgressRow): CellText {
  return {
    primary: String(row.channel ?? "").trim() || "Unknown channel",
    secondary: channelRoleLabel(row.meta.role),
  };
}

export function musicCellText(row: ProgressRow): CellText {
  const meta = row.meta;
  const base = meaningful(row.music) ?? `${meta.saved ?? 0}/${Math.max(1, meta.expected ?? 0)} downloaded`;
  const pending = meta.download_pending ?? 0;
  const ready = meta.download_ready ?? 0;
  let secondary: string | null = null;
  if (pending > 0) secondary = `${pending} pending`;
  else if (ready > 0) secondary = `${ready} ready`;
  return { primary: base, secondary };
}

export function imageCellText(row: ProgressRow, manualMode: boolean): CellText {
  const meta = row.meta;
  const counts = `BG ${meta.bg_ready ?? 0}/${meta.bg_total ?? 0} · TH ${meta.th_ready ?? 0}/${meta.th_total ?? 0}`;
  const mode = manualMode || String(meta.source_mode ?? "").toLowerCase() === "manual" ? "Manual mode" : "Auto mode";
  const failures: string[] = [];
  if (String(meta.bg_status ?? "").toUpperCase() === "FAILED") failures.push("BG failed");
  if (String(meta.th_status ?? "").toUpperCase() === "FAILED") failures.push("TH failed");
  return {
    primary: counts,
    secondary: failures.length ? `${mode} · ${failures.join(", ")}` : mode,
  };
}

export function youtubeCellText(row: ProgressRow): CellText & { url: string | null; tone: ProgressTone } {
  const meta = row.meta;
  const api = meaningful(row.youtube);
  const status = String(meta.youtube_status ?? "").toUpperCase();
  let primary = api ?? "Not started";
  let tone = statusBadgeTone(api ?? "not started");
  if ((meta.youtube_failed ?? 0) > 0 || status === "FAILED") {
    primary = "Failed";
    tone = "danger";
  } else if (status === "BLOCKED") {
    primary = "Blocked";
    tone = "danger";
  } else if ((meta.youtube_pending ?? 0) > 0) {
    primary = api ?? "Uploading";
    tone = "accent";
  } else if ((meta.youtube_success ?? 0) > 0) {
    primary = api ?? "Completed";
    tone = "success";
  }
  const url = meaningful(meta.youtube_url);
  if (url && tone === "neutral") tone = "success";
  return { primary, secondary: url, url, tone };
}

export function notesText(row: ProgressRow): string | null {
  const note = meaningful(row.notes);
  if (note) return note;
  const meta = row.meta;
  const messages: string[] = [];
  if (String(meta.bg_status ?? "").toUpperCase() === "FAILED") messages.push("Background image failed");
  if (String(meta.th_status ?? "").toUpperCase() === "FAILED") messages.push("Thumbnail image failed");
  if ((meta.youtube_failed ?? 0) > 0) messages.push("YouTube upload failed");
  if ((meta.draft_failed_song_ids?.length ?? 0) > 0) {
    messages.push(`${meta.draft_failed_song_ids?.length} draft failure`);
  }
  if ((meta.suno_failed_song_ids?.length ?? 0) > 0) {
    messages.push(`${meta.suno_failed_song_ids?.length} Suno failure`);
  }
  return messages.length ? messages.join(" · ") : null;
}

export function formatAbsoluteTime(value: string | null | undefined): string | null {
  if (!value) return null;
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return null;
  return new Intl.DateTimeFormat("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  }).format(parsed);
}

export function relativeTime(value: string | null | undefined, now = Date.now()): string {
  if (!value) return "Not reported";
  const parsed = Date.parse(value);
  if (Number.isNaN(parsed)) return "Not reported";
  const seconds = Math.max(0, Math.round((now - parsed) / 1000));
  if (seconds < 60) return "<1m ago";
  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.floor(hours / 24);
  if (days < 14) return `${days}d ago`;
  return formatAbsoluteTime(value) ?? "Not reported";
}

export function updatedCellText(row: ProgressRow, now = Date.now()): CellText {
  const absoluteValue = row.meta.updated_at;
  const absolute = formatAbsoluteTime(absoluteValue);
  if (absoluteValue && absolute) {
    return { primary: relativeTime(absoluteValue, now), secondary: null, title: absolute };
  }
  return { primary: meaningful(row.updated) ?? "Not reported", secondary: null };
}

export type TimelineState = "passed" | "current" | "pending" | "failed" | "unavailable";

export interface TimelineStep {
  key: "music" | "image" | "converter" | "merge" | "youtube";
  label: string;
  state: TimelineState;
  detail: string;
}

const TIMELINE_RANKS: Record<string, number> = {
  music: 1,
  image: 2,
  converter: 3,
  merger: 4,
  youtube: 5,
  done: 6,
  completed: 6,
  error: 7,
};

function timelineRank(stage: string): number {
  return TIMELINE_RANKS[stageKey(stage)] ?? 0;
}

function inferFailureStage(row: ProgressRow): "music" | "image" | "converter" | "merge" | "youtube" | null {
  const text = `${row.stage} ${row.status} ${row.notes} ${row.music} ${row.image} ${row.converter} ${row.merge} ${row.youtube}`.toLowerCase();
  if (text.includes("youtube") && (text.includes("fail") || text.includes("error") || text.includes("blocked"))) {
    return "youtube";
  }
  if ((text.includes("merge") || text.includes("merger")) && (text.includes("fail") || text.includes("error"))) {
    return "merge";
  }
  if ((text.includes("converter") || text.includes("export")) && (text.includes("fail") || text.includes("error"))) {
    return "converter";
  }
  if (text.includes("image") && (text.includes("fail") || text.includes("error"))) return "image";
  if (text.includes("music") && (text.includes("fail") || text.includes("error"))) return "music";
  return null;
}

export function stageTimeline(row: ProgressRow, manualMode: boolean): TimelineStep[] {
  const status = normalizeStatus(row.status);
  const failed = stageKey(row.stage) === "error" || status === "failed" || status === "blocked";
  const failureStage = failed ? inferFailureStage(row) : null;
  const currentRank = timelineRank(row.stage);
  const failureRank = failureStage ? Math.max(1, timelineRank(failureStage)) : 0;
  const video = localVideoState(row);

  return (
    [
      { key: "music", label: "Music", detail: musicCellText(row).primary },
      { key: "image", label: "Image", detail: imageCellText(row, manualMode).primary },
      { key: "converter", label: "Converter", detail: video.converter ?? PIPELINE_MISSING },
      { key: "merge", label: "Merge", detail: video.merge ?? PIPELINE_MISSING },
      { key: "youtube", label: "YouTube", detail: youtubeCellText(row).primary },
    ] as const
  ).map((step) => {
    const rank = TIMELINE_RANKS[step.key];
    if (failed) {
      if (failureStage === step.key) {
        return { ...step, state: "failed" as const, detail: statusLabel(row.status) };
      }
      if (failureRank > rank) return { ...step, state: "passed" as const };
      return { ...step, state: "pending" as const };
    }
    if (currentRank > rank) return { ...step, state: "passed" as const };
    if (currentRank === rank) {
      if (stageKey(row.stage) === "done" || stageKey(row.stage) === "completed") {
        return { ...step, state: "passed" as const };
      }
      return { ...step, state: "current" as const, detail: statusLabel(row.status) };
    }
    if (
      (step.key === "converter" || step.key === "merge") &&
      video.source === "none"
    ) {
      return { ...step, state: "unavailable" as const };
    }
    return { ...step, state: "pending" as const };
  });
}

export function failureStageLabel(row: ProgressRow): string | null {
  const failed = stageKey(row.stage) === "error" || normalizeStatus(row.status) === "failed";
  if (!failed) return null;
  const stage = inferFailureStage(row);
  if (!stage) return null;
  return stage === "converter" ? "Converter" : stage === "merge" ? "Merge" : stage.charAt(0).toUpperCase() + stage.slice(1);
}

/* ------------------------------------------------------------------ */
/* Download queue (PG-39…PG-43)                                        */
/* ------------------------------------------------------------------ */

export function downloadStateLabel(state: DownloadItemState): string {
  switch (state) {
    case "queued":
      return "Queued";
    case "downloading":
      return "Downloading";
    case "done":
      return "Done";
    case "failed":
      return "Failed";
    case "cancelled":
      return "Cancelled";
  }
}

export function downloadStateTone(state: DownloadItemState): ProgressTone {
  switch (state) {
    case "downloading":
      return "accent";
    case "done":
      return "success";
    case "failed":
      return "danger";
    case "cancelled":
      return "warning";
    default:
      return "neutral";
  }
}

export function formatBytes(bytes: number | null | undefined): string {
  if (bytes == null || !Number.isFinite(bytes) || bytes < 0) return "--";
  if (bytes < 1024) return `${Math.round(bytes)} B`;
  const units = ["KB", "MB", "GB", "TB"] as const;
  let value = bytes / 1024;
  let index = 0;
  while (value >= 1024 && index < units.length - 1) {
    value /= 1024;
    index += 1;
  }
  return `${value >= 10 ? value.toFixed(0) : value.toFixed(1)} ${units[index]}`;
}

export function downloadProgressText(item: DownloadItemInfo): string {
  switch (item.state) {
    case "downloading": {
      if (item.totalBytes && item.totalBytes > 0) {
        const percent =
          item.percent ?? Math.min(100, Math.round((item.receivedBytes / item.totalBytes) * 100));
        return `${formatBytes(item.receivedBytes)} / ${formatBytes(item.totalBytes)} · ${percent}%`;
      }
      return item.receivedBytes > 0 ? `${formatBytes(item.receivedBytes)} downloaded` : "Starting…";
    }
    case "done":
      if (item.totalBytes && item.totalBytes > 0) return formatBytes(item.totalBytes);
      if (item.receivedBytes > 0) return formatBytes(item.receivedBytes);
      return "Saved";
    case "failed":
      return "Not saved";
    case "cancelled":
      return "Stopped";
    default:
      return "Waiting for a slot";
  }
}

export function parentFolder(filePath: string | null | undefined): string | null {
  const trimmed = filePath?.trim().replace(/[\\/]+$/, "") ?? "";
  if (!trimmed) return null;
  const index = Math.max(trimmed.lastIndexOf("\\"), trimmed.lastIndexOf("/"));
  return index > 0 ? trimmed.slice(0, index) : null;
}

export interface DownloadQueueRow {
  key: string;
  taskId: string;
  song: string;
  subtitle: string | null;
  channel: string;
  path: string;
  folderPath: string | null;
  state: string;
  stateTone: ProgressTone;
  progress: string;
  error: string | null;
  showRetry: boolean;
  canRetry: boolean;
  canCancel: boolean;
  canReveal: boolean;
  hasUrl: boolean;
}

/** PG-40: one row per pending target, merged with the coordinator's live state. */
export function downloadQueueRows(
  items: DownloadItemInfo[],
  progressRows: ProgressRow[],
): DownloadQueueRow[] {
  const channels = new Map<string, string>();
  for (const row of progressRows) {
    if (row.batch && row.channel) channels.set(row.batch, row.channel);
  }

  return items.map((item) => {
    const batch = meaningful(item.batchId);
    const track = item.trackNumber != null ? `Track ${item.trackNumber}` : null;
    const subtitle =
      [track, batch].filter((part): part is string => Boolean(part)).join(" · ") || null;
    return {
      key: item.key,
      taskId: item.taskId,
      song: meaningful(item.title) ?? meaningful(item.songId) ?? item.taskId,
      subtitle,
      channel: (batch && channels.get(batch)) || batch || "Unknown channel",
      path: meaningful(item.targetPath) ?? "Not reported",
      folderPath: parentFolder(item.targetPath),
      state: downloadStateLabel(item.state),
      stateTone: downloadStateTone(item.state),
      progress: downloadProgressText(item),
      error: meaningful(item.error),
      showRetry: item.state === "failed" || item.state === "cancelled",
      canRetry: (item.state === "failed" || item.state === "cancelled") && item.hasUrl,
      canCancel: item.state === "queued" || item.state === "downloading",
      canReveal: item.state === "done" && Boolean(item.targetPath),
      hasUrl: item.hasUrl,
    };
  });
}
