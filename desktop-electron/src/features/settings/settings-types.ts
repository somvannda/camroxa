import type { ChannelProfile } from "../dashboard/account-types";

/**
 * Pure Settings workspace logic: draft shapes, normalisation, API payloads,
 * validation and small formatters.
 *
 * The field names mirror the platform settings keys used by the Python
 * desktop client (`shared/lib/settings_workspace.py`) so a value written here
 * is read by the same pipeline when it runs.
 */

export type SettingsTab = "profiles" | "publication" | "preferences";

export const SETTINGS_TABS: Array<{ id: SettingsTab; label: string }> = [
  { id: "profiles", label: "Profiles" },
  { id: "publication", label: "Publication" },
  { id: "preferences", label: "Preferences" },
];

export type OutputResolution = "1920x1080" | "1080x1920" | "1080x1080" | "1280x720";

export const OUTPUT_RESOLUTIONS: Array<{ value: OutputResolution; label: string }> = [
  { value: "1920x1080", label: "1920 × 1080" },
  { value: "1080x1920", label: "1080 × 1920" },
  { value: "1080x1080", label: "1080 × 1080" },
  { value: "1280x720", label: "1280 × 720" },
];

export type ImageMode = "bg_thumb" | "bg_only" | "thumb_only";

export const IMAGE_MODES: Array<{ value: ImageMode; label: string }> = [
  { value: "bg_thumb", label: "BG + TH" },
  { value: "bg_only", label: "BG Only" },
  { value: "thumb_only", label: "TH Only" },
];

export type Visibility = "public" | "unlisted" | "private" | "scheduled";

export const VISIBILITY_OPTIONS: Array<{ value: Visibility; label: string }> = [
  { value: "public", label: "Public" },
  { value: "unlisted", label: "Unlisted" },
  { value: "private", label: "Private" },
  { value: "scheduled", label: "Scheduled" },
];

export const PUBLICATION_CATEGORIES: Array<{ value: string; label: string }> = [
  { value: "10", label: "Music" },
  { value: "24", label: "Entertainment" },
  { value: "22", label: "People & Blogs" },
  { value: "20", label: "Gaming" },
  { value: "1", label: "Film & Animation" },
  { value: "2", label: "Autos & Vehicles" },
  { value: "15", label: "Pets & Animals" },
  { value: "17", label: "Sports" },
  { value: "19", label: "Travel & Events" },
  { value: "26", label: "Howto & Style" },
  { value: "27", label: "Education" },
];

export const YOUTUBE_CHUNK_SIZES = [128, 256, 512] as const;

export const MAX_WORKER_TOTAL = 12;

export type KindSource = "prompt_only" | "category" | "admin_library";

export const KIND_SOURCES: Array<{ value: KindSource; label: string }> = [
  { value: "prompt_only", label: "Prompt only" },
  { value: "category", label: "Category" },
  { value: "admin_library", label: "Admin library" },
];

export type ThumbnailGeneration = "background_text" | "composite";

export const THUMBNAIL_GENERATIONS: Array<{ value: ThumbnailGeneration; label: string }> = [
  { value: "background_text", label: "AI text on background" },
  { value: "composite", label: "Composite (legacy)" },
];

export const HOURS: Array<{ value: string; label: string }> = Array.from({ length: 24 }, (_, index) => {
  const value = String(index).padStart(2, "0");
  return { value, label: value };
});

export const MINUTES: Array<{ value: string; label: string }> = Array.from({ length: 12 }, (_, index) => {
  const value = String(index * 5).padStart(2, "0");
  return { value, label: value };
});

// ---------------------------------------------------------------------------
// Generic helpers
// ---------------------------------------------------------------------------

export function deepEqual(left: unknown, right: unknown): boolean {
  if (left === right) return true;
  if (typeof left !== typeof right || left === null || right === null) return false;
  if (typeof left !== "object") return false;
  if (Array.isArray(left) || Array.isArray(right)) {
    if (!Array.isArray(left) || !Array.isArray(right)) return false;
    if (left.length !== right.length) return false;
    return left.every((item, index) => deepEqual(item, right[index]));
  }
  const leftRecord = left as Record<string, unknown>;
  const rightRecord = right as Record<string, unknown>;
  const leftKeys = Object.keys(leftRecord);
  const rightKeys = Object.keys(rightRecord);
  if (leftKeys.length !== rightKeys.length) return false;
  return leftKeys.every(
    (key) => Object.prototype.hasOwnProperty.call(rightRecord, key) && deepEqual(leftRecord[key], rightRecord[key]),
  );
}

export function clamp(value: number, minimum: number, maximum: number): number {
  return Math.min(maximum, Math.max(minimum, value));
}

export function recordOf(value: unknown): Record<string, unknown> {
  return value && typeof value === "object" && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : {};
}

export function readStringSetting(
  settings: Record<string, unknown> | null | undefined,
  key: string,
  fallback = "",
): string {
  const value = (settings ?? {})[key];
  return typeof value === "string" ? value : fallback;
}

export function readNumberSetting(
  settings: Record<string, unknown> | null | undefined,
  key: string,
  fallback: number,
): number {
  const value = (settings ?? {})[key];
  if (typeof value === "number" && Number.isFinite(value)) return value;
  if (typeof value === "string" && value.trim()) {
    const parsed = Number(value);
    if (Number.isFinite(parsed)) return parsed;
  }
  return fallback;
}

export function readBooleanSetting(
  settings: Record<string, unknown> | null | undefined,
  key: string,
  fallback = false,
): boolean {
  const value = (settings ?? {})[key];
  if (typeof value === "boolean") return value;
  if (typeof value === "string") {
    const normalized = value.trim().toLowerCase();
    if (normalized === "true" || normalized === "1" || normalized === "yes") return true;
    if (normalized === "false" || normalized === "0" || normalized === "no") return false;
  }
  return fallback;
}

export function parseCommaList(value: string): string[] {
  return value
    .split(",")
    .map((part) => part.trim())
    .filter(Boolean);
}

export function listToCommaText(value: unknown): string {
  if (Array.isArray(value)) {
    return value.filter((item) => typeof item === "string" && item.trim()).join(", ");
  }
  if (typeof value === "string") return value;
  return "";
}

// ---------------------------------------------------------------------------
// Profile
// ---------------------------------------------------------------------------

export interface ProfileDraft {
  name: string;
  folderName: string;
  runPrefix: string;
  outputResolution: OutputResolution;
  imageMode: ImageMode;
  logoPath: string;
  logoBase64: string | null;
  logoPreview: string | null;
  coverPath: string;
  coverBase64: string | null;
  coverPreview: string | null;
}

export function normalizeImageMode(value: unknown): ImageMode {
  const mode = String(value ?? "").trim().toLowerCase();
  if (mode === "bg_only" || mode === "thumb_only") return mode;
  return "bg_thumb";
}

export function normalizeOutputResolution(value: unknown): OutputResolution {
  const text = String(value ?? "").trim().toLowerCase();
  const match = OUTPUT_RESOLUTIONS.find((option) => option.value === text);
  return match?.value ?? "1920x1080";
}

export function slugifyProfileFolder(name: string): string {
  let folder = String(name ?? "")
    .trim()
    .toLowerCase()
    .replace(/\s+/g, "-")
    .replace(/\//g, "-");
  folder = Array.from(folder)
    .filter((character) => /[a-z0-9-]/.test(character))
    .join("");
  while (folder.includes("--")) folder = folder.replace(/--/g, "-");
  folder = folder.replace(/^-+|-+$/g, "");
  return (folder.slice(0, 50) || "profile");
}

export function resolveProfileFolderName(name: string, folderName: string): string {
  const cleaned = String(folderName ?? "").trim();
  if (cleaned) return cleaned.slice(0, 50);
  return slugifyProfileFolder(name);
}

export function profileInitials(name: string): string {
  const parts = String(name ?? "")
    .trim()
    .split(/\s+/)
    .filter(Boolean);
  return parts
    .slice(0, 2)
    .map((part) => part[0]?.toUpperCase() ?? "")
    .join("") || "P";
}

export function emptyProfileDraft(): ProfileDraft {
  return {
    name: "",
    folderName: "",
    runPrefix: "",
    outputResolution: "1920x1080",
    imageMode: "bg_thumb",
    logoPath: "",
    logoBase64: null,
    logoPreview: null,
    coverPath: "",
    coverBase64: null,
    coverPreview: null,
  };
}

export function buildProfileDraft(profile: ChannelProfile | null | undefined): ProfileDraft {
  if (!profile) return emptyProfileDraft();
  const imageConfig = recordOf(profile.image_config);
  const coverPaths = Array.isArray(imageConfig.cover_paths) ? imageConfig.cover_paths : [];
  const coverPath = coverPaths.find((item): item is string => typeof item === "string" && Boolean(item)) ?? "";
  return {
    name: profile.name ?? "",
    folderName: profile.folder_name ?? "",
    runPrefix: profile.run_prefix ?? "",
    outputResolution: normalizeOutputResolution(profile.output_resolution),
    imageMode: normalizeImageMode(imageConfig.mode),
    logoPath: profile.logo_path ?? "",
    logoBase64: null,
    logoPreview: null,
    coverPath,
    coverBase64: null,
    coverPreview: null,
  };
}

export function profileDraftDirty(draft: ProfileDraft, baseline: ProfileDraft): boolean {
  return !deepEqual(draft, baseline);
}

export function buildProfilePayload(draft: ProfileDraft): Record<string, unknown> {
  const payload: Record<string, unknown> = {
    name: draft.name.trim(),
    folder_name: resolveProfileFolderName(draft.name, draft.folderName),
    run_prefix: draft.runPrefix.trim(),
    output_resolution: draft.outputResolution,
    // The API merges image_config with the stored object, so server-owned keys
    // such as cover_paths survive when only the mode is sent.
    image_config: { mode: draft.imageMode },
  };
  if (draft.logoBase64) payload.logo_base64 = draft.logoBase64;
  if (draft.coverBase64) payload.cover_images = [draft.coverBase64];
  return payload;
}

export function profileSearchHaystack(profile: ChannelProfile): string {
  return [profile.name, profile.folder_name ?? "", profile.run_prefix ?? ""]
    .filter(Boolean)
    .join(" ")
    .toLowerCase();
}

export function filterProfiles(profiles: ChannelProfile[], term: string): ChannelProfile[] {
  const needle = term.trim().toLowerCase();
  const sorted = [...profiles].sort((left, right) =>
    String(left.name ?? "").localeCompare(String(right.name ?? ""), undefined, { sensitivity: "base" }),
  );
  if (!needle) return sorted;
  return sorted.filter((profile) => profileSearchHaystack(profile).includes(needle));
}

export type ProfileField = "name" | "folderName" | "runPrefix";

const SAFE_NAME = /^[A-Za-z0-9._-]*$/;

export function validateProfileDraft(
  draft: ProfileDraft,
  profiles: ChannelProfile[],
  currentProfileId: string | null,
): Partial<Record<ProfileField, string>> {
  const errors: Partial<Record<ProfileField, string>> = {};
  const name = draft.name.trim();
  if (!name) {
    errors.name = "Enter a profile name.";
  } else if (name.length > 100) {
    errors.name = "Use 100 characters or fewer.";
  } else {
    const clash = profiles.find(
      (profile) =>
        profile.id !== currentProfileId &&
        String(profile.name ?? "").trim().toLowerCase() === name.toLowerCase(),
    );
    if (clash) errors.name = "A profile with this name already exists.";
  }

  const folder = draft.folderName.trim();
  if (folder) {
    if (folder.length > 50) errors.folderName = "Use 50 characters or fewer.";
    else if (!SAFE_NAME.test(folder)) {
      errors.folderName = "Use letters, numbers, dots, dashes and underscores only.";
    } else {
      const clash = profiles.find(
        (profile) =>
          profile.id !== currentProfileId &&
          String(profile.folder_name ?? "").trim().toLowerCase() === folder.toLowerCase(),
      );
      if (clash) errors.folderName = `The folder name is already used by ${clash.name}.`;
    }
  }

  const prefix = draft.runPrefix.trim();
  if (prefix && !SAFE_NAME.test(prefix)) {
    errors.runPrefix = "Use letters, numbers, dots, dashes and underscores only.";
  }

  return errors;
}

// ---------------------------------------------------------------------------
// Publication
// ---------------------------------------------------------------------------

export interface PublicationDraft {
  description: string;
  keywords: string;
  visibility: Visibility;
  publishHour: string;
  publishMinute: string;
  madeForKids: boolean;
  aiUse: boolean;
  category: string;
  playlist: string;
  tags: string;
  titleTemplate: string;
  descriptionTemplate: string;
}

export function normalizeVisibility(value: unknown): Visibility {
  const text = String(value ?? "").trim().toLowerCase();
  const match = VISIBILITY_OPTIONS.find((option) => option.value === text);
  return match?.value ?? "unlisted";
}

export function splitPublishAt(value: unknown): { hour: string; minute: string } {
  const text = String(value ?? "").trim();
  const match = text.match(/^(?:(\d{4}-\d{2}-\d{2})[T ])?(\d{1,2}):(\d{2})/);
  if (!match) return { hour: "00", minute: "00" };
  const hour = clamp(Number(match[2]), 0, 23);
  const minute = Math.floor(clamp(Number(match[3]), 0, 59) / 5) * 5;
  return {
    hour: String(hour).padStart(2, "0"),
    minute: String(minute).padStart(2, "0"),
  };
}

export function emptyPublicationDraft(): PublicationDraft {
  return {
    description: "",
    keywords: "",
    visibility: "unlisted",
    publishHour: "00",
    publishMinute: "00",
    madeForKids: false,
    aiUse: false,
    category: "10",
    playlist: "",
    tags: "",
    titleTemplate: "",
    descriptionTemplate: "",
  };
}

export function buildPublicationDraft(profile: ChannelProfile | null | undefined): PublicationDraft {
  const config = recordOf(profile?.youtube_config);
  const schedule = splitPublishAt(config.publish_at);
  const category = String(config.category ?? "10").trim() || "10";
  return {
    description: typeof config.description === "string" ? config.description : "",
    keywords: listToCommaText(config.keywords),
    visibility: normalizeVisibility(config.visibility),
    publishHour: schedule.hour,
    publishMinute: schedule.minute,
    madeForKids: Boolean(config.made_for_kids),
    aiUse: Boolean(config.ai_use),
    category: PUBLICATION_CATEGORIES.some((option) => option.value === category) ? category : "10",
    playlist: typeof config.playlist === "string" ? config.playlist : "",
    tags: listToCommaText(config.tags),
    titleTemplate: typeof config.title_template === "string" ? config.title_template : "",
    descriptionTemplate:
      typeof config.description_template === "string" ? config.description_template : "",
  };
}

export function publicationDraftDirty(draft: PublicationDraft, baseline: PublicationDraft): boolean {
  return !deepEqual(draft, baseline);
}

export function buildPublicationPayload(
  draft: PublicationDraft,
  baseConfig: Record<string, unknown> | null | undefined,
): Record<string, unknown> {
  return {
    ...(baseConfig ?? {}),
    description: draft.description.trim(),
    keywords: parseCommaList(draft.keywords),
    visibility: draft.visibility,
    publish_at: draft.visibility === "scheduled" ? `${draft.publishHour}:${draft.publishMinute}` : null,
    made_for_kids: draft.madeForKids,
    ai_use: draft.aiUse,
    category: draft.category.trim(),
    playlist: draft.playlist.trim(),
    tags: parseCommaList(draft.tags),
    title_template: draft.titleTemplate.trim(),
    description_template: draft.descriptionTemplate.trim(),
  };
}

export type PublicationField =
  | "description"
  | "keywords"
  | "tags"
  | "titleTemplate"
  | "descriptionTemplate"
  | "playlist"
  | "publishHour"
  | "publishMinute";

export interface PublicationValidationContext {
  connected: boolean;
  playlistsLoaded: boolean;
  playlists: Array<{ id: string }>;
}

export const MAX_KEYWORDS_CHARS = 500;
export const MAX_TAGS_COUNT = 15;
export const MAX_TITLE_TEMPLATE_CHARS = 100;
export const MAX_DESCRIPTION_CHARS = 5000;

export function validatePublicationDraft(
  draft: PublicationDraft,
  context: PublicationValidationContext,
): Partial<Record<PublicationField, string>> {
  const errors: Partial<Record<PublicationField, string>> = {};

  if (draft.description.trim().length > MAX_DESCRIPTION_CHARS) {
    errors.description = `Use ${MAX_DESCRIPTION_CHARS} characters or fewer.`;
  }

  const keywords = parseCommaList(draft.keywords);
  const keywordLength = keywords.join(", ").length;
  if (keywordLength > MAX_KEYWORDS_CHARS) {
    errors.keywords = `Keywords exceed ${MAX_KEYWORDS_CHARS} characters (${keywordLength}).`;
  }

  const tags = parseCommaList(draft.tags);
  if (tags.length > MAX_TAGS_COUNT) {
    errors.tags = `Use ${MAX_TAGS_COUNT} tags or fewer.`;
  } else if (tags.join(", ").length > MAX_KEYWORDS_CHARS) {
    errors.tags = `Tags exceed ${MAX_KEYWORDS_CHARS} characters.`;
  }

  if (draft.titleTemplate.trim().length > MAX_TITLE_TEMPLATE_CHARS) {
    errors.titleTemplate = `Keep the title template within ${MAX_TITLE_TEMPLATE_CHARS} characters.`;
  }
  if (draft.descriptionTemplate.trim().length > MAX_DESCRIPTION_CHARS) {
    errors.descriptionTemplate = `Keep the description template within ${MAX_DESCRIPTION_CHARS} characters.`;
  }

  if (draft.visibility === "scheduled") {
    const hour = Number(draft.publishHour);
    const minute = Number(draft.publishMinute);
    if (!Number.isInteger(hour) || hour < 0 || hour > 23) {
      errors.publishHour = "Pick an hour between 00 and 23.";
    }
    if (!Number.isInteger(minute) || minute < 0 || minute > 59) {
      errors.publishMinute = "Pick a minute between 00 and 59.";
    }
  }

  const playlist = draft.playlist.trim();
  if (
    context.connected &&
    context.playlistsLoaded &&
    context.playlists.length > 0 &&
    playlist &&
    !context.playlists.some((option) => option.id === playlist)
  ) {
    errors.playlist = "That playlist is not on the channel. Pick another one or create a new playlist.";
  }

  return errors;
}

export interface TemplateValues {
  title?: string;
  album?: string;
  channel?: string;
}

export function renderTemplate(template: string, values: TemplateValues): string {
  let text = String(template ?? "");
  const title = values.title ?? "";
  const album = values.album ?? title;
  const channel = values.channel ?? "";
  text = text.split("{title}").join(title);
  text = text.split("{album}").join(album);
  text = text.split("{channel}").join(channel);
  return text.replace(/\s+/g, " ").trim();
}

export function scheduleSummary(draft: PublicationDraft, now: Date = new Date()): string {
  if (draft.visibility !== "scheduled") return "";
  const hour = Number(draft.publishHour);
  const minute = Number(draft.publishMinute);
  if (!Number.isInteger(hour) || !Number.isInteger(minute)) return "";
  const target = new Date(now.getTime());
  target.setHours(hour, minute, 0, 0);
  if (target.getTime() <= now.getTime()) target.setDate(target.getDate() + 1);
  return new Intl.DateTimeFormat(undefined, {
    weekday: "short",
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
    timeZoneName: "short",
  }).format(target);
}

// ---------------------------------------------------------------------------
// Preferences
// ---------------------------------------------------------------------------

export interface PreferencesDraft {
  ffmpegPath: string;
  sunoOutputDir: string;
  musicWorkers: number;
  imageWorkers: number;
  exportWorkers: number;
  mergeWorkers: number;
  youtubeWorkers: number;
  chunkSizeMb: number;
  outputResolution: OutputResolution;
  styleStrength: number;
  imageSourceMode: "ai" | "manual";
  backgroundSource: KindSource;
  thumbnailSource: KindSource;
  thumbnailGeneration: ThumbnailGeneration;
}

export function normalizeImageSourceMode(value: unknown): "ai" | "manual" {
  return String(value ?? "").trim().toLowerCase() === "manual" ? "manual" : "ai";
}

export function normalizeKindSourceMode(value: unknown): "prompt_only" | "category" {
  const text = String(value ?? "").trim().toLowerCase();
  return text === "prompt" || text === "prompt_only" ? "prompt_only" : "category";
}

export function resolveKindSource(modeValue: unknown, promptSourceValue: unknown): KindSource {
  if (String(promptSourceValue ?? "").trim().toLowerCase() === "admin_library") return "admin_library";
  return normalizeKindSourceMode(modeValue);
}

export function kindSourceSettings(source: KindSource): { mode: "prompt_only" | "category"; promptSource: string } {
  if (source === "admin_library") return { mode: "prompt_only", promptSource: "admin_library" };
  if (source === "prompt_only") return { mode: "prompt_only", promptSource: "custom" };
  return { mode: "category", promptSource: "custom" };
}

export function imagePromptLibraryOnly(settings: Record<string, unknown> | null | undefined): boolean {
  return readBooleanSetting(settings, "imagePromptLibraryOnly", false);
}

export function defaultPreferencesDraft(): PreferencesDraft {
  return {
    ffmpegPath: "",
    sunoOutputDir: "",
    musicWorkers: 1,
    imageWorkers: 4,
    exportWorkers: 1,
    mergeWorkers: 1,
    youtubeWorkers: 1,
    chunkSizeMb: 256,
    outputResolution: "1920x1080",
    styleStrength: 80,
    imageSourceMode: "ai",
    backgroundSource: "category",
    thumbnailSource: "category",
    thumbnailGeneration: "background_text",
  };
}

export function buildPreferencesDraft(settings: Record<string, unknown> | null | undefined): PreferencesDraft {
  const raw = settings ?? {};
  const libraryOnly = readBooleanSetting(raw, "imagePromptLibraryOnly", false);
  const legacyBackground = String(raw.backgroundSourceMode ?? "").trim().toLowerCase();
  const backgroundMode = raw.imageBackgroundSourceMode
    ? raw.imageBackgroundSourceMode
    : legacyBackground === "prompt" || legacyBackground === "prompt_only"
      ? "prompt_only"
      : "category";
  const chunk = readNumberSetting(raw, "youtubeUploadChunkSizeMb", 256);
  const thumbnailGeneration = String(raw.thumbnailReferenceMode ?? "").trim().toLowerCase();

  return {
    ffmpegPath: readStringSetting(raw, "ffmpegPath"),
    sunoOutputDir: readStringSetting(raw, "sunoOutputDir"),
    musicWorkers: clamp(Math.round(readNumberSetting(raw, "perfMusicWorkers", 1)), 1, 5),
    imageWorkers: clamp(Math.round(readNumberSetting(raw, "perfImageWorkers", 4)), 1, 8),
    exportWorkers: clamp(
      Math.round(
        readNumberSetting(raw, "videoExportWorkers", readNumberSetting(raw, "perfExportWorkers", 1)),
      ),
      1,
      10,
    ),
    mergeWorkers: clamp(Math.round(readNumberSetting(raw, "perfMergeWorkers", 1)), 1, 2),
    youtubeWorkers: clamp(Math.round(readNumberSetting(raw, "perfYouTubeWorkers", 1)), 1, 5),
    chunkSizeMb: chunk === 128 || chunk === 512 ? chunk : 256,
    outputResolution: normalizeOutputResolution(
      readStringSetting(raw, "outputResolution") || readStringSetting(raw, "imageResolution"),
    ),
    styleStrength: clamp(Math.round(readNumberSetting(raw, "styleStrength", 80)), 0, 100),
    imageSourceMode: normalizeImageSourceMode(raw.imageSourceMode),
    backgroundSource: libraryOnly
      ? "admin_library"
      : resolveKindSource(backgroundMode, raw.imageBackgroundPromptSource ?? "custom"),
    thumbnailSource: libraryOnly
      ? "admin_library"
      : resolveKindSource(
          raw.imageThumbnailSourceMode ?? "category",
          raw.imageThumbnailPromptSource ?? "custom",
        ),
    thumbnailGeneration: thumbnailGeneration === "composite" ? "composite" : "background_text",
  };
}

export function preferencesDraftDirty(draft: PreferencesDraft, baseline: PreferencesDraft): boolean {
  return !deepEqual(draft, baseline);
}

/** Produce the minimal settings patch for the changed fields only. */
export function buildPreferencesPatch(
  draft: PreferencesDraft,
  baseline: PreferencesDraft,
): Record<string, unknown> {
  const patch: Record<string, unknown> = {};

  const stringKeys: Array<[keyof PreferencesDraft, string]> = [
    ["ffmpegPath", "ffmpegPath"],
    ["sunoOutputDir", "sunoOutputDir"],
  ];
  for (const [field, key] of stringKeys) {
    if (draft[field] !== baseline[field]) patch[key] = String(draft[field]).trim();
  }

  const numberKeys: Array<[keyof PreferencesDraft, string]> = [
    ["musicWorkers", "perfMusicWorkers"],
    ["imageWorkers", "perfImageWorkers"],
    ["mergeWorkers", "perfMergeWorkers"],
    ["youtubeWorkers", "perfYouTubeWorkers"],
    ["chunkSizeMb", "youtubeUploadChunkSizeMb"],
    ["styleStrength", "styleStrength"],
  ];
  for (const [field, key] of numberKeys) {
    if (draft[field] !== baseline[field]) patch[key] = Number(draft[field]);
  }

  if (draft.exportWorkers !== baseline.exportWorkers) {
    patch.perfExportWorkers = draft.exportWorkers;
    patch.videoExportWorkers = draft.exportWorkers;
  }

  if (draft.outputResolution !== baseline.outputResolution) {
    patch.outputResolution = draft.outputResolution;
    patch.imageResolution = draft.outputResolution;
  }

  if (draft.imageSourceMode !== baseline.imageSourceMode) {
    patch.imageSourceMode = draft.imageSourceMode;
  }

  if (draft.backgroundSource !== baseline.backgroundSource) {
    const resolved = kindSourceSettings(draft.backgroundSource);
    patch.imageBackgroundSourceMode = resolved.mode;
    patch.imageBackgroundPromptSource = resolved.promptSource;
  }

  if (draft.thumbnailSource !== baseline.thumbnailSource) {
    const resolved = kindSourceSettings(draft.thumbnailSource);
    patch.imageThumbnailSourceMode = resolved.mode;
    patch.imageThumbnailPromptSource = resolved.promptSource;
  }

  if (draft.thumbnailGeneration !== baseline.thumbnailGeneration) {
    patch.thumbnailReferenceMode = draft.thumbnailGeneration;
  }

  return patch;
}

export function validatePreferencesDraft(
  draft: PreferencesDraft,
): Partial<Record<keyof PreferencesDraft, string>> {
  const errors: Partial<Record<keyof PreferencesDraft, string>> = {};
  const bounds: Array<[keyof PreferencesDraft, number, number, string]> = [
    ["musicWorkers", 1, 5, "Music workers must be between 1 and 5."],
    ["imageWorkers", 1, 8, "Image workers must be between 1 and 8."],
    ["exportWorkers", 1, 10, "Export workers must be between 1 and 10."],
    ["mergeWorkers", 1, 2, "Merge workers must be between 1 and 2."],
    ["youtubeWorkers", 1, 5, "YouTube workers must be between 1 and 5."],
    ["styleStrength", 0, 100, "Style strength must be between 0 and 100."],
  ];
  for (const [field, minimum, maximum, message] of bounds) {
    const value = Number(draft[field]);
    if (!Number.isInteger(value) || value < minimum || value > maximum) errors[field] = message;
  }
  if (![128, 256, 512].includes(Number(draft.chunkSizeMb))) {
    errors.chunkSizeMb = "Choose a 128, 256 or 512 MB chunk size.";
  }
  return errors;
}

export interface FfmpegStatus {
  state: "idle" | "checking" | "available" | "missing" | "unavailable";
  message: string;
}

export function totalWorkers(draft: PreferencesDraft): number {
  return (
    draft.musicWorkers +
    draft.imageWorkers +
    draft.exportWorkers +
    draft.mergeWorkers +
    draft.youtubeWorkers
  );
}

export function workerLoadWarning(draft: PreferencesDraft): string | null {
  const total = totalWorkers(draft);
  if (total <= MAX_WORKER_TOTAL) return null;
  return `Total worker count is ${total}. Above ${MAX_WORKER_TOTAL} the machine can slow down while a batch runs.`;
}

export function countDirtyTabs(flags: Record<SettingsTab, boolean>): number {
  return SETTINGS_TABS.filter((tab) => flags[tab.id]).length;
}

export function dirtyTabLabel(tabs: SettingsTab[]): string {
  if (tabs.length === 0) return "No unsaved changes.";
  const labels = SETTINGS_TABS.filter((tab) => tabs.includes(tab.id)).map((tab) => tab.label);
  const noun = tabs.length === 1 ? "tab" : "tabs";
  return `${tabs.length} ${noun} with unsaved changes: ${labels.join(", ")}.`;
}
