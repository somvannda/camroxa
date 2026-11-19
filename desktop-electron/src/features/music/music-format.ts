import type { ChannelProfile, DraftSeeds, HistoryFilters, MusicHistoryBatch, MusicHistorySong } from "./music-types";

export function todayYmd(now: Date = new Date()): string {
  const year = now.getFullYear();
  const month = String(now.getMonth() + 1).padStart(2, "0");
  const day = String(now.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
}

function parseYmd(value: string): Date | null {
  const match = /^(\d{4})-(\d{2})-(\d{2})/.exec(value.trim());
  if (!match) return null;
  const date = new Date(Number(match[1]), Number(match[2]) - 1, Number(match[3]));
  return Number.isNaN(date.getTime()) ? null : date;
}

export function inclusiveDaySpan(fromDate: string, toDate: string): number | null {
  if (!fromDate || !toDate) return null;
  const start = parseYmd(fromDate);
  const end = parseYmd(toDate);
  if (!start || !end) return null;
  const days = Math.round((end.getTime() - start.getTime()) / 86_400_000) + 1;
  return days > 0 ? days : null;
}

export function inclusiveDateList(fromDate: string, toDate: string): string[] {
  const span = inclusiveDaySpan(fromDate, toDate);
  const start = parseYmd(fromDate);
  if (!span || !start) return [];
  return Array.from({ length: span }, (_, index) => {
    const date = new Date(start.getTime() + index * 86_400_000);
    return todayYmd(date);
  });
}

export function plannedDaysText(fromDate: string, toDate: string): string {
  const span = inclusiveDaySpan(fromDate, toDate);
  if (span === null) return "Choose a valid inclusive date range.";
  return `${span} planned ${span === 1 ? "day" : "days"}`;
}

export interface EffectPreview {
  valence: number;
  danceability: number;
  instrumentalness: number;
}

export function effectPreview(creativity: number): EffectPreview {
  const value = Math.min(100, Math.max(0, Math.round(creativity)));
  return {
    valence: Math.min(95, Math.max(5, Math.round(20 + value * 0.7))),
    danceability: Math.min(95, Math.max(5, Math.round(15 + value * 0.75))),
    instrumentalness: Math.min(95, Math.max(5, Math.round(10 + value * 0.55))),
  };
}

export function extractOpening(lyrics: string | null | undefined): string | null {
  if (!lyrics) return null;
  for (const line of lyrics.split(/\r?\n/)) {
    const trimmed = line.trim();
    if (trimmed && !trimmed.startsWith("[")) return trimmed;
  }
  return null;
}

/**
 * Avoid lists use the newest `ceil(window / 10)` batches (50 → 5), capped at
 * 200 entries per list, matching the 1.7.1 helper.
 */
export function buildHistoryAvoidLists(
  batches: MusicHistoryBatch[] | null | undefined,
  historyWindow: number,
): { titles: string[]; albums: string[]; openings: string[] } {
  const titles = new Set<string>();
  const albums = new Set<string>();
  const openings = new Set<string>();
  const limit = Math.max(1, Math.ceil(historyWindow / 10));
  for (const batch of (batches ?? []).slice(0, limit)) {
    for (const song of batch.songs ?? []) {
      const title = (song.title ?? "").trim();
      const album = (song.album ?? "").trim();
      const opening = extractOpening(song.lyrics);
      if (title) titles.add(title);
      if (album) albums.add(album);
      if (opening) openings.add(opening);
    }
  }
  return {
    titles: [...titles].slice(0, 200),
    albums: [...albums].slice(0, 200),
    openings: [...openings].slice(0, 200),
  };
}

export function buildDraftDescription(base: string, seeds: DraftSeeds | null): string {
  if (!seeds) return base;
  const inspiration = [seeds.titleSeed, seeds.albumSeed].filter(Boolean).join(" / ");
  if (!inspiration) return base;
  return `${base}\n\nInspiration (do not copy words): ${inspiration}`.trim();
}

export function buildReservationToken(): string {
  try {
    if (typeof crypto !== "undefined" && typeof crypto.randomUUID === "function") {
      return crypto.randomUUID();
    }
  } catch {
    // fall through to the deterministic fallback
  }
  return `pool-${Date.now()}-${Math.random().toString(36).slice(2, 10)}`;
}

export interface PlannedRunDirectories {
  okRunDir: string;
  altRunDir: string;
  runFolderName: string;
}

function sanitizeSegment(value: string): string {
  return (
    value
      .split("")
      .filter((character) => character.charCodeAt(0) >= 32)
      .join("")
      .replace(/[<>:"/\\|?*]+/g, "-")
      .replace(/\s+/g, " ")
      .trim()
      .replace(/\.+$/, "")
      .slice(0, 80) || "item"
  );
}

function sanitizeRunLabel(value: string): string {
  return (
    value
      .replace(/[^a-zA-Z0-9 _.-]+/g, "")
      .replace(/\s+/g, " ")
      .trim()
      .replace(/ /g, "-")
      .slice(0, 64) || "run"
  );
}

function joinWindowsPath(...segments: string[]): string {
  const parts: string[] = [];
  segments.forEach((segment, index) => {
    const normalized = String(segment ?? "").replace(/\//g, "\\");
    parts.push(index === 0 ? normalized.replace(/\\+$/, "") : normalized.replace(/^\\+|\\+$/g, ""));
  });
  return parts.filter(Boolean).join("\\");
}

export function planManualRunDirectories(input: {
  baseDir: string;
  okProfileFolder: string;
  altProfileFolder: string;
  runLabel: string;
}): PlannedRunDirectories {
  const base = input.baseDir.trim().replace(/[\\/]+$/, "");
  if (!base) return { okRunDir: "", altRunDir: "", runFolderName: "" };
  const runFolderName = sanitizeRunLabel(input.runLabel);
  return {
    okRunDir: joinWindowsPath(base, sanitizeSegment(input.okProfileFolder), runFolderName),
    altRunDir: joinWindowsPath(base, sanitizeSegment(input.altProfileFolder), runFolderName),
    runFolderName,
  };
}

export function toggleSelection(selected: string[], profileId: string): string[] {
  if (!profileId) return selected;
  return selected.includes(profileId)
    ? selected.filter((id) => id !== profileId)
    : [...selected, profileId];
}

export function sanitizeSelection(
  selected: string[],
  profiles: ChannelProfile[],
  fallback: string[],
): string[] {
  const valid = new Set(profiles.map((profile) => profile.id));
  const deduped = selected.filter((id, index) => valid.has(id) && selected.indexOf(id) === index);
  if (deduped.length > 0) return deduped;
  return fallback.filter((id, index) => valid.has(id) && fallback.indexOf(id) === index);
}

export interface PairValidation {
  mismatch: boolean;
  overlap: boolean;
  canPair: boolean;
}

export function validatePairs(primaryIds: string[], secondaryIds: string[]): PairValidation {
  const overlap = primaryIds.some((id) => secondaryIds.includes(id));
  const mismatch = primaryIds.length !== secondaryIds.length;
  return { mismatch, overlap, canPair: !overlap && !mismatch && primaryIds.length > 0 };
}

export interface HistoryRow {
  key: string;
  rowNumber: number;
  batchIndex: number;
  batch: MusicHistoryBatch;
  song: MusicHistorySong;
}

function ymd(value: string | null | undefined): string {
  const text = String(value ?? "").trim();
  return text.length >= 10 && text[4] === "-" && text[7] === "-" ? text.slice(0, 10) : "";
}

function batchWindow(batch: MusicHistoryBatch): [string, string] | null {
  const start = ymd(batch.from_date) || ymd(batch.created_at);
  if (!start) return null;
  const end = ymd(batch.to_date) || start;
  return end < start ? [end, start] : [start, end];
}

export function matchesHistoryDateRange(
  batch: MusicHistoryBatch,
  fromDate: string,
  toDate: string,
): boolean {
  let from = ymd(fromDate);
  let to = ymd(toDate);
  if (from && to && to < from) [from, to] = [to, from];
  if (!from && !to) return true;
  const lower = from || "0001-01-01";
  const upper = to || "9999-12-31";
  const window = batchWindow(batch);
  if (window && window[1] >= lower && window[0] <= upper) return true;
  const created = ymd(batch.created_at);
  return Boolean(created && created >= lower && created <= upper);
}

export function matchesHistoryFilters(
  batch: MusicHistoryBatch,
  filters: HistoryFilters,
  batchIndex: number,
): boolean {
  if (filters.lastBatchOnly) return batchIndex === 0;
  return matchesHistoryDateRange(batch, filters.fromDate, filters.toDate);
}

export function flattenHistory(
  batches: MusicHistoryBatch[] | null | undefined,
  filters: HistoryFilters,
): HistoryRow[] {
  const rows: HistoryRow[] = [];
  let rowNumber = 1;
  (batches ?? []).forEach((batch, batchIndex) => {
    if (!matchesHistoryFilters(batch, filters, batchIndex)) return;
    for (const song of batch.songs ?? []) {
      rows.push({
        key: `${batch.batch_id}:${song.song_id}`,
        rowNumber,
        batchIndex,
        batch,
        song,
      });
      rowNumber += 1;
    }
  });
  return rows;
}

export function historySummary(
  batches: MusicHistoryBatch[] | null | undefined,
  rows: HistoryRow[],
  apiSummary?: string,
): string {
  const loadedBatches = (batches ?? []).length;
  const loadedSongs = (batches ?? []).reduce((total, batch) => total + (batch.songs?.length ?? 0), 0);
  if (loadedSongs === 0) return "";
  if (rows.length === loadedSongs) {
    return apiSummary || `${loadedBatches} batches · ${loadedSongs} songs`;
  }
  const batchCount = new Set(rows.map((row) => row.batch.batch_id)).size;
  return `${batchCount} ${batchCount === 1 ? "batch" : "batches"} · ${rows.length} ${
    rows.length === 1 ? "song" : "songs"
  } shown (of ${loadedBatches} loaded)`;
}

export function songFolder(song: MusicHistorySong, side: "primary" | "secondary"): string {
  return (side === "primary" ? song.output_dir_ok : song.output_dir_alt)?.trim() ?? "";
}

export function batchStatusText(status: {
  status: string;
  drafts_completed: number;
  total_songs: number;
  suno_submitted: number;
  suno_completed: number;
  suno_failed: number;
}): string {
  const parts = [status.status.replace(/_/g, " ")];
  if (status.total_songs > 0) parts.push(`${status.drafts_completed}/${status.total_songs} drafts`);
  if (status.suno_submitted > 0 || status.suno_completed > 0 || status.suno_failed > 0) {
    parts.push(`${status.suno_completed}/${status.total_songs} Suno`);
  }
  return parts.join(" · ");
}

export function isTerminalBatchStatus(status: string): boolean {
  return ["completed", "partial", "failed"].includes(status);
}

export interface CreateBatchesOutcome {
  planned: number;
  dayCount: number;
  pairCount: number;
  created: Array<{ date: string; okName: string; altName: string }>;
  failed: Array<{ date: string; okName: string; altName: string; message: string }>;
}

export function createBatchesSummary(outcome: CreateBatchesOutcome): string {
  const batchWord = outcome.created.length === 1 ? "batch run" : "batch runs";
  const dayWord = outcome.dayCount === 1 ? "planned day" : "planned days";
  const pairWord = outcome.pairCount === 1 ? "channel pair" : "channel pairs";
  const base =
    outcome.created.length > 0
      ? `Created ${outcome.created.length} ${batchWord} across ${outcome.dayCount} ${dayWord} and ${outcome.pairCount} ${pairWord}.`
      : "No batch runs were created.";
  if (outcome.failed.length === 0) return base;
  const missing = outcome.failed
    .map((slot) => `${slot.date} · ${slot.okName} ↔ ${slot.altName}`)
    .join("; ");
  return `${base} Still missing: ${missing}.`;
}
