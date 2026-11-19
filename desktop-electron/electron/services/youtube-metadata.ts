/**
 * Publication metadata for the manual YouTube upload (ported from
 * `camxora_python/shared/lib/youtube_direct.py`).
 *
 * Everything here is pure: the caller passes the profile's `youtube_config`
 * and the merged-file path, and gets the exact snippet/status YouTube and the
 * platform publish job receive. No token, email or cookie ever enters this
 * module.
 */
import path from "node:path";

export const CATEGORY_MUSIC = "10";
export const MAX_TITLE_CHARS = 100;
export const MAX_DESCRIPTION_CHARS = 5000;
export const MAX_TAG_CHARS = 60;
export const MAX_TAGS_TOTAL_CHARS = 500;

export type YoutubeVisibility = "private" | "unlisted" | "public" | "scheduled";

const VISIBILITIES: ReadonlySet<string> = new Set<YoutubeVisibility>([
  "private",
  "unlisted",
  "public",
  "scheduled",
]);

/**
 * YouTube rejects the whole upload when a keyword is invalid: tags may not
 * contain angle brackets, must be non-empty, and the list is capped at 500
 * characters in total.
 */
export function sanitizeTags(raw: unknown): string[] {
  let candidates: string[];
  if (typeof raw === "string") {
    candidates = raw.split(",");
  } else if (Array.isArray(raw)) {
    candidates = raw.map((item) => String(item));
  } else {
    candidates = [];
  }

  const tags: string[] = [];
  const seen = new Set<string>();
  let total = 0;
  for (const candidate of candidates) {
    let text = String(candidate)
      .replace(/[<>]/g, "")
      .split(/\s+/)
      .filter(Boolean)
      .join(" ")
      .trim();
    if (!text) continue;
    if (text.length > MAX_TAG_CHARS) text = text.slice(0, MAX_TAG_CHARS).trimEnd();
    const key = text.toLowerCase();
    if (seen.has(key)) continue;
    if (total + text.length + 1 > MAX_TAGS_TOTAL_CHARS) break;
    seen.add(key);
    tags.push(text);
    total += text.length + 1;
  }
  return tags;
}

/** `2026-11-19_Night Shift` → `Night Shift`; a bare file name falls back to its stem. */
export function albumFromPath(videoPath: string): string {
  const parent = path.basename(path.dirname(String(videoPath ?? "")));
  const stem = parent.includes("_") ? parent.slice(parent.indexOf("_") + 1) : parent;
  const cleaned = stem.replace(/[-_]/g, " ").trim();
  return cleaned || path.basename(String(videoPath ?? ""), path.extname(String(videoPath ?? "")));
}

/** `{title}`, `{album}` and `{channel}` tokens, whitespace collapsed. */
export function renderTemplate(
  template: string | null | undefined,
  values: { album: string; channel: string },
): string {
  let text = String(template ?? "").trim();
  if (!text) text = "{title}";
  const replacements: Array<[string, string]> = [
    ["{title}", values.album],
    ["{album}", values.album],
    ["{channel}", values.channel],
  ];
  for (const [token, value] of replacements) text = text.split(token).join(value);
  return text.split(/\s+/).filter(Boolean).join(" ");
}

/**
 * `publish_at` is either a full ISO timestamp (passed through) or a local
 * `HH:MM` that schedules the next occurrence in UTC. Anything else is ignored,
 * so a bad setting never silently publishes immediately.
 */
export function nextPublishAt(raw: unknown, now: Date = new Date()): string | null {
  const text = String(raw ?? "").trim();
  if (!text) return null;
  if (text.includes("T")) return text;
  const match = /^(\d{1,2}):(\d{2})$/.exec(text);
  if (!match) return null;
  const hour = Number(match[1]);
  const minute = Number(match[2]);
  if (hour > 23 || minute > 59) return null;
  const target = new Date(now.getTime());
  target.setHours(hour, minute, 0, 0);
  if (target.getTime() <= now.getTime()) target.setDate(target.getDate() + 1);
  return target.toISOString().replace(/\.\d{3}Z$/, "Z");
}

export interface YoutubeProfileInput {
  id: string;
  name: string;
  youtubeConfig?: Record<string, unknown> | null;
}

export interface PublicationMetadata {
  title: string;
  description: string;
  tags: string[];
  visibility: YoutubeVisibility;
  publishAt: string | null;
  category: string;
  madeForKids: boolean;
  containsSyntheticMedia: boolean;
  playlistId: string;
  thumbnailPath: string | null;
}

function configOf(profile: YoutubeProfileInput): Record<string, unknown> {
  const config = profile.youtubeConfig;
  return config && typeof config === "object" ? config : {};
}

function boolOf(value: unknown): boolean {
  if (typeof value === "boolean") return value;
  if (typeof value === "string") return ["1", "true", "yes", "on"].includes(value.trim().toLowerCase());
  return false;
}

/** Publication settings from Settings → Publication, rendered for one file. */
export function buildMetadata(input: {
  profile: YoutubeProfileInput;
  videoPath: string;
  thumbnailPath?: string | null;
  now?: Date;
}): PublicationMetadata {
  const config = configOf(input.profile);
  const album = albumFromPath(input.videoPath);
  const channel = String(input.profile.name ?? "").trim();

  const title =
    renderTemplate(String(config.title_template ?? ""), { album, channel }).slice(
      0,
      MAX_TITLE_CHARS,
    ) || album.slice(0, MAX_TITLE_CHARS);
  const description = renderTemplate(String(config.description_template ?? ""), {
    album,
    channel,
  }).slice(0, MAX_DESCRIPTION_CHARS);

  const configured = String(config.visibility ?? "private").trim().toLowerCase();
  const visibility: YoutubeVisibility = VISIBILITIES.has(configured)
    ? (configured as YoutubeVisibility)
    : "private";

  return {
    title: title || path.basename(input.videoPath, path.extname(input.videoPath)).slice(0, MAX_TITLE_CHARS),
    description,
    tags: sanitizeTags(config.tags),
    visibility,
    publishAt: visibility === "scheduled" ? nextPublishAt(config.publish_at, input.now) : null,
    category: String(config.category ?? CATEGORY_MUSIC).trim() || CATEGORY_MUSIC,
    madeForKids: boolOf(config.made_for_kids),
    containsSyntheticMedia: boolOf(config.ai_use),
    playlistId: String(config.playlist ?? "").trim(),
    thumbnailPath: input.thumbnailPath ?? null,
  };
}

/** A scheduled video is uploaded private with `publishAt`, as Studio shows it. */
export function youtubeStatusBody(metadata: PublicationMetadata): Record<string, unknown> {
  const scheduled = metadata.visibility === "scheduled" && Boolean(metadata.publishAt);
  const status: Record<string, unknown> = {
    privacyStatus: scheduled ? "private" : metadata.visibility,
    selfDeclaredMadeForKids: metadata.madeForKids,
    containsSyntheticMedia: metadata.containsSyntheticMedia,
  };
  if (scheduled) status.publishAt = metadata.publishAt;
  return status;
}

/** The `videos.insert` body YouTube receives with the resumable session. */
export function youtubeInsertBody(metadata: PublicationMetadata): Record<string, unknown> {
  return {
    snippet: {
      title: metadata.title,
      description: metadata.description,
      tags: metadata.tags,
      categoryId: metadata.category || CATEGORY_MUSIC,
    },
    status: youtubeStatusBody(metadata),
  };
}

export interface PublishJobPayload {
  profile_id: string;
  platform: "youtube";
  batch_id: string | null;
  role: string;
  title: string;
  description: string | null;
  tags: string[];
  privacy_status: string;
  publish_at: string | null;
  made_for_kids: boolean;
  contains_synthetic_media: boolean;
  file_name: string;
  file_size_bytes: number | null;
  file_path: string;
  thumbnail_path: string | null;
}

/** `POST /publish/jobs` body; mirrors `CreatePublishJobRequest`. */
export function buildPublishJobPayload(input: {
  profileId: string;
  batchId: string | null;
  role: string;
  metadata: PublicationMetadata;
  filePath: string;
  fileSizeBytes?: number | null;
}): PublishJobPayload {
  const metadata = input.metadata;
  return {
    profile_id: input.profileId,
    platform: "youtube",
    batch_id: input.batchId ? input.batchId.trim() || null : null,
    role: (String(input.role ?? "").trim().toUpperCase() || "OK"),
    title: metadata.title,
    description: metadata.description || null,
    tags: metadata.tags,
    privacy_status: metadata.visibility,
    publish_at: metadata.publishAt,
    made_for_kids: metadata.madeForKids,
    contains_synthetic_media: metadata.containsSyntheticMedia,
    file_name: path.basename(input.filePath),
    file_size_bytes: input.fileSizeBytes ?? null,
    file_path: input.filePath,
    thumbnail_path: metadata.thumbnailPath,
  };
}

export function videoUrl(videoId: string): string {
  return `https://www.youtube.com/watch?v=${encodeURIComponent(videoId)}`;
}

/** Studio-ish label used in the confirmation dialog. */
export function visibilityLabel(metadata: PublicationMetadata): string {
  if (metadata.visibility === "scheduled") {
    return metadata.publishAt
      ? `Scheduled · ${metadata.publishAt}`
      : "Scheduled (no time set — uploads private)";
  }
  return metadata.visibility.charAt(0).toUpperCase() + metadata.visibility.slice(1);
}
