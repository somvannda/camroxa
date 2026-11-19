import type {
  ChannelProfile,
  ImageJobListItem,
  ImageSettings,
  MusicHistoryBatch,
} from "./image-types";

/** Mirrors platform_api's IMAGE_MAX_PROMPT_LENGTH. */
export const IMAGE_PROMPT_MAX_CHARS = 20_000;

export type StatusTone = "success" | "warning" | "danger" | "neutral";

export interface QueueRow {
  key: string;
  batchId: string;
  songId: string;
  albumLabel: string;
  trackCount: number;
  dateLabel: string;
  profileName: string;
  role: string;
  bgJob: ImageJobListItem | null;
  thJob: ImageJobListItem | null;
  bgJobs: ImageJobListItem[];
  thJobs: ImageJobListItem[];
}

export interface QueueSummary {
  rows: number;
  pending: number;
  running: number;
  failed: number;
  ready: number;
  text: string;
}

const STATUS_RANK: Record<string, number> = {
  success: 4,
  running: 3,
  pending: 2,
  failed: 1,
  cancelled: 0,
};

function statusRank(status: string | null | undefined): number {
  return STATUS_RANK[String(status ?? "").trim().toLowerCase()] ?? -1;
}

function jobSortKey(job: ImageJobListItem): [number, string] {
  return [statusRank(job.status), String(job.updated_at || job.created_at || "")];
}

export function pickPreferredJob(
  current: ImageJobListItem | null,
  candidate: ImageJobListItem,
): ImageJobListItem {
  if (!current) return candidate;
  const [candidateRank, candidateTime] = jobSortKey(candidate);
  const [currentRank, currentTime] = jobSortKey(current);
  if (candidateRank !== currentRank) return candidateRank > currentRank ? candidate : current;
  return candidateTime >= currentTime ? candidate : current;
}

export function clampPrompt(text: string): string {
  return text.length <= IMAGE_PROMPT_MAX_CHARS ? text : text.slice(0, IMAGE_PROMPT_MAX_CHARS);
}

/**
 * Background falls back to the legacy shared `imagePrompt`; thumbnail has no
 * legacy equivalent, so it stays empty. Mirrors `normalize_image_prompt_settings`.
 */
export function normalizeImagePrompts(settings: ImageSettings | null | undefined): {
  background: string;
  thumbnail: string;
} {
  const raw = settings ?? {};
  const legacy = typeof raw.imagePrompt === "string" ? raw.imagePrompt : "";
  return {
    background: clampPrompt(
      typeof raw.imageBackgroundPrompt === "string" ? raw.imageBackgroundPrompt : legacy,
    ),
    thumbnail: clampPrompt(typeof raw.imageThumbnailPrompt === "string" ? raw.imageThumbnailPrompt : ""),
  };
}

export function todayYmd(now: Date = new Date()): string {
  const month = String(now.getMonth() + 1).padStart(2, "0");
  const day = String(now.getDate()).padStart(2, "0");
  return `${now.getFullYear()}-${month}-${day}`;
}

function batchFromDate(batch: MusicHistoryBatch): string {
  return (batch.from_date || batch.created_at || "").slice(0, 10);
}

function batchToDate(batch: MusicHistoryBatch): string {
  return (batch.to_date || batch.updated_at || batch.created_at || "").slice(0, 10);
}

export function batchDateLabel(batch: MusicHistoryBatch): string {
  const from = batchFromDate(batch) || "Unknown date";
  const to = batchToDate(batch) || from;
  return from === to ? from : `${from} → ${to}`;
}

/** Inclusive range check on the batch date span. */
export function batchIsWithinRange(
  batch: MusicHistoryBatch,
  fromDate: string,
  toDate: string,
): boolean {
  const batchFrom = batchFromDate(batch);
  const batchTo = batchToDate(batch);
  if (fromDate && batchTo && batchTo < fromDate) return false;
  if (toDate && batchFrom && batchFrom > toDate) return false;
  return true;
}

export function filterBatchesByDate(
  batches: MusicHistoryBatch[],
  fromDate: string,
  toDate: string,
): MusicHistoryBatch[] {
  return batches.filter((batch) => batchIsWithinRange(batch, fromDate, toDate));
}

export function filterJobsByBatchIds(
  jobs: ImageJobListItem[],
  batchIds: Set<string>,
): ImageJobListItem[] {
  if (batchIds.size === 0) return [];
  return jobs.filter((job) => Boolean(job.batch_id) && batchIds.has(String(job.batch_id)));
}

/**
 * Fallback when `/music/history` fails: derive a minimal batch per job so the
 * queue still renders with dates instead of silently disappearing.
 */
export function deriveBatchesFromJobs(jobs: ImageJobListItem[]): MusicHistoryBatch[] {
  const batches = new Map<string, MusicHistoryBatch>();
  for (const job of jobs) {
    const batchId = job.batch_id ? String(job.batch_id) : "";
    if (!batchId || batches.has(batchId)) continue;
    const date = (job.created_at || job.updated_at || "").slice(0, 10);
    batches.set(batchId, {
      batch_id: batchId,
      status: "unknown",
      song_count: 0,
      from_date: date,
      to_date: date,
      created_at: job.created_at,
      updated_at: job.updated_at,
      songs: [],
    });
  }
  return [...batches.values()];
}

function albumFallback(batch: MusicHistoryBatch): string {
  for (const song of batch.songs ?? []) {
    const album = String(song.album ?? "").trim();
    if (album) return album;
  }
  for (const song of batch.songs ?? []) {
    const title = String(song.title ?? "").trim();
    if (title) return title;
  }
  const status = String(batch.status ?? "").trim().toLowerCase();
  return status === "manual_image" ? "Not available" : "Untitled album";
}

export function buildAlbumLabels(
  batches: MusicHistoryBatch[],
): Map<string, { ok: string; alt: string }> {
  const labels = new Map<string, { ok: string; alt: string }>();
  for (const batch of batches) {
    const fallback = albumFallback(batch);
    const manual = String(batch.status ?? "").trim().toLowerCase() === "manual_image";
    let ok = String(batch.ok_album ?? "").trim() || (manual ? "Not available" : fallback);
    if (ok.toLowerCase() === "not available") ok = "Not available";
    let alt = String(batch.alt_album ?? "").trim();
    if (!alt || alt.toLowerCase() === ok.toLowerCase()) alt = `${ok} II`;
    labels.set(batch.batch_id, { ok, alt });
  }
  return labels;
}

/**
 * One row per `{batch}-{profile}-{role}`, with the best background and thumbnail
 * job in the same row. Mirrors `build_queue_rows`.
 */
export function buildQueueRows(
  jobs: ImageJobListItem[],
  batches: MusicHistoryBatch[],
  profiles: ChannelProfile[],
): QueueRow[] {
  const profileById = new Map(profiles.map((profile) => [profile.id, profile]));
  const batchById = new Map(batches.map((batch) => [batch.batch_id, batch]));
  const albumLabels = buildAlbumLabels(batches);
  const rows = new Map<string, QueueRow>();

  for (const job of jobs) {
    const batchId = job.batch_id ?? "";
    const profileId = job.profile_id ?? "";
    const role = job.channel_role ?? "";
    const key = `${batchId}-${profileId}-${role}`;
    const batch = batchById.get(batchId);
    const isManual = String(batch?.status ?? "").trim().toLowerCase() === "manual_image";
    const profileName = isManual
      ? "Not available"
      : profileById.get(profileId)?.name || profileId || "Unknown";
    const displayRole = isManual ? "n/a" : role;

    const existing = rows.get(key) ?? {
      key,
      batchId,
      songId: job.song_id ?? "",
      albumLabel: albumLabels.get(batchId)?.ok ?? "Untitled album",
      trackCount: batch?.song_count ?? batch?.songs?.length ?? 0,
      dateLabel: batch ? batchDateLabel(batch) : "Unknown date",
      profileName,
      role: displayRole,
      bgJob: null,
      thJob: null,
      bgJobs: [],
      thJobs: [],
    };

    if (!existing.songId && job.song_id) existing.songId = job.song_id;
    if (job.kind === "background") {
      existing.bgJobs.push(job);
      existing.bgJob = pickPreferredJob(existing.bgJob, job);
    } else if (job.kind === "thumbnail") {
      existing.thJobs.push(job);
      existing.thJob = pickPreferredJob(existing.thJob, job);
    }
    rows.set(key, existing);
  }

  return [...rows.values()].sort((a, b) => {
    const byDate = a.dateLabel.localeCompare(b.dateLabel);
    if (byDate) return byDate;
    const byAlbum = a.albumLabel.localeCompare(b.albumLabel);
    if (byAlbum) return byAlbum;
    const byRole = a.role.localeCompare(b.role);
    if (byRole) return byRole;
    return a.profileName.localeCompare(b.profileName);
  });
}

export function summarizeQueue(rows: QueueRow[]): QueueSummary {
  const jobs = rows.flatMap((row) => [...row.bgJobs, ...row.thJobs]);
  const count = (status: string) =>
    jobs.filter((job) => String(job.status ?? "").toLowerCase() === status).length;
  const pending = count("pending");
  const running = count("running");
  const failed = count("failed");
  const ready = count("success");
  return {
    rows: rows.length,
    pending,
    running,
    failed,
    ready,
    text: `Rows ${rows.length} · Pending ${pending} · Running ${running} · Failed ${failed} · Ready ${ready}`,
  };
}

export function statusTone(status: string | null | undefined): StatusTone {
  switch (String(status ?? "").trim().toLowerCase()) {
    case "success":
    case "completed":
      return "success";
    case "running":
    case "processing":
      return "warning";
    case "failed":
    case "error":
      return "danger";
    default:
      return "neutral";
  }
}

export function formatJobStatus(status: string | null | undefined): string {
  const normalized = String(status ?? "").trim().toLowerCase();
  return normalized || "—";
}

export function basenameOrDash(path: string | null | undefined): string {
  if (!path) return "—";
  const normalized = path.replace(/\\/g, "/");
  const name = normalized.split("/").filter(Boolean).pop();
  return name || "—";
}

export function buildFooterDetail(row: QueueRow | null): string {
  if (!row) return "";
  const parts: string[] = [];
  if (row.trackCount > 1) parts.push(`${row.trackCount} tracks in batch`);
  const bgErrors = [...new Set(row.bgJobs.map((job) => String(job.error ?? "").trim()).filter(Boolean))];
  const thErrors = [...new Set(row.thJobs.map((job) => String(job.error ?? "").trim()).filter(Boolean))];
  if (bgErrors.length) parts.push(`BG error: ${bgErrors[0]}`);
  if (thErrors.length) parts.push(`TH error: ${thErrors[0]}`);
  if (row.bgJob?.input_image_path) {
    parts.push(`BG sample: ${basenameOrDash(row.bgJob.input_image_path)}`);
  }
  if (row.thJob?.style_reference_path) {
    parts.push(`TH style: ${basenameOrDash(row.thJob.style_reference_path)}`);
  }
  return parts.join(" · ");
}

export function splitFooterDetail(detail: string): { info: string; errors: string } {
  const info: string[] = [];
  const errors: string[] = [];
  for (const part of detail.split(" · ")) {
    const text = part.trim();
    if (!text || /tracks in batch/i.test(text)) continue;
    if (/^(bg|th) error:/i.test(text)) errors.push(text);
    else info.push(text);
  }
  return { info: info.join(" · "), errors: errors.join(" · ") };
}

export function emptyQueueMessage(
  totalJobs: number,
  filteredBatchCount: number,
  filteredJobCount: number,
): string {
  if (totalJobs === 0) return "No image jobs yet.";
  if (filteredBatchCount === 0) return "No batches found in the selected date range.";
  if (filteredJobCount === 0) return "No image jobs yet for this date range.";
  return "No image jobs match the current filters.";
}

/**
 * The preview target for a row: the preferred job's output path, with the
 * other job of the same kind as a fallback when the preferred file is gone.
 */
export function previewCandidates(row: QueueRow | null, kind: "background" | "thumbnail"): string[] {
  if (!row) return [];
  const jobs = kind === "background" ? row.bgJobs : row.thJobs;
  return jobs
    .map((job) => job.output_image_path)
    .filter((path): path is string => Boolean(path));
}

export function bytesToDataUrl(bytes: Uint8Array, mime: string): string {
  let binary = "";
  const chunk = 0x8000;
  for (let index = 0; index < bytes.length; index += chunk) {
    binary += String.fromCharCode(...bytes.subarray(index, index + chunk));
  }
  return `data:${mime || "image/png"};base64,${btoa(binary)}`;
}
