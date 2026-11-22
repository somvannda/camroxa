import type { SettingsRecord } from "./music-types";

export interface MusicSettings {
  language: string;
  secondaryLanguage: string;
  creativity: number;
  uniqueOpening: boolean;
  useContentPools: boolean;
  strictLevel: number;
  historyWindow: number;
  songCount: number;
  simpleMode: boolean;
  autoGenImage: boolean;
  autoGSuno: boolean;
  autoVideoAfterSuno: boolean;
  autoMergeAfterVideo: boolean;
  autoReelAfterVideo: boolean;
  autoUploadYouTube: boolean;
  polishStrength: number;
  shuffleStructure: boolean;
  shuffleMood: boolean;
  skipExistingBatches: boolean;
  /** Saved Primary/Secondary channel pairing for the Music page. */
  primaryProfileIds: string[];
  secondaryProfileIds: string[];
}

export const LANGUAGE_OPTIONS = [
  { value: "en", label: "English" },
  { value: "km", label: "Khmer" },
  { value: "de", label: "German" },
  { value: "es", label: "Spanish" },
  { value: "fr", label: "French" },
] as const;

export const HISTORY_WINDOW_OPTIONS = [50, 100, 200, 500, 1500] as const;

export const DEFAULT_MUSIC_SETTINGS: MusicSettings = {
  language: "en",
  secondaryLanguage: "",
  creativity: 55,
  uniqueOpening: false,
  useContentPools: false,
  strictLevel: 3,
  historyWindow: 100,
  songCount: 4,
  simpleMode: false,
  autoGenImage: false,
  autoGSuno: false,
  autoVideoAfterSuno: false,
  autoMergeAfterVideo: false,
  autoReelAfterVideo: false,
  autoUploadYouTube: false,
  polishStrength: 85,
  shuffleStructure: false,
  shuffleMood: false,
  skipExistingBatches: false,
  primaryProfileIds: [],
  secondaryProfileIds: [],
};

export const SONG_COUNT_MIN = 1;
export const SONG_COUNT_MAX = 50;
export const LYRIC_LIMIT = 20_000;

export function clamp(value: number, minimum: number, maximum: number): number {
  return Math.min(maximum, Math.max(minimum, value));
}

function readBoolean(settings: SettingsRecord, key: string, fallback: boolean): boolean {
  const value = settings[key];
  if (typeof value === "boolean") return value;
  if (typeof value === "string") {
    const normalised = value.trim().toLowerCase();
    if (["true", "on", "yes", "1"].includes(normalised)) return true;
    if (["false", "off", "no", "0"].includes(normalised)) return false;
  }
  return fallback;
}

function readNumber(settings: SettingsRecord, key: string, fallback: number): number {
  const value = settings[key];
  if (typeof value === "number" && Number.isFinite(value)) return Math.trunc(value);
  if (typeof value === "string" && value.trim()) {
    const parsed = Number.parseFloat(value);
    if (Number.isFinite(parsed)) return Math.trunc(parsed);
  }
  return fallback;
}

function readString(settings: SettingsRecord, key: string, fallback = ""): string {
  const value = settings[key];
  if (value === null || value === undefined) return fallback;
  const text = String(value).trim();
  return text || fallback;
}

/** Settings store arrays as JSON; older values may arrive as JSON strings. */
function readStringArray(settings: SettingsRecord, key: string): string[] {
  const value = settings[key];
  let parsed: unknown = value;
  if (typeof value === "string") {
    try {
      parsed = JSON.parse(value);
    } catch {
      return [];
    }
  }
  if (!Array.isArray(parsed)) return [];
  return parsed
    .map((item) => (typeof item === "string" ? item.trim() : ""))
    .filter((item) => item.length > 0);
}

export function normaliseLanguage(value: string | undefined): string {
  const normalised = (value ?? "").trim().toLowerCase();
  return LANGUAGE_OPTIONS.some((option) => option.value === normalised)
    ? normalised
    : LANGUAGE_OPTIONS[0].value;
}

export function buildMusicSettings(settings: SettingsRecord | null | undefined): MusicSettings {
  const raw = settings ?? {};
  const requestedWindow = clamp(
    readNumber(raw, "uniquenessHistoryWindow", DEFAULT_MUSIC_SETTINGS.historyWindow),
    50,
    1500,
  );
  const historyWindow = HISTORY_WINDOW_OPTIONS.includes(
    requestedWindow as (typeof HISTORY_WINDOW_OPTIONS)[number],
  )
    ? requestedWindow
    : HISTORY_WINDOW_OPTIONS.reduce((closest, option) =>
        Math.abs(option - requestedWindow) < Math.abs(closest - requestedWindow) ? option : closest,
      );
  return {
    language: normaliseLanguage(readString(raw, "language")),
    secondaryLanguage: readString(raw, "secondaryLanguage").toLowerCase(),
    creativity: clamp(
      readNumber(raw, "creativity", DEFAULT_MUSIC_SETTINGS.creativity),
      0,
      100,
    ),
    uniqueOpening: readBoolean(raw, "uniqueOpening", DEFAULT_MUSIC_SETTINGS.uniqueOpening),
    useContentPools: readBoolean(
      raw,
      "useContentPools",
      DEFAULT_MUSIC_SETTINGS.useContentPools,
    ),
    strictLevel: clamp(
      readNumber(raw, "strictLevel", DEFAULT_MUSIC_SETTINGS.strictLevel),
      1,
      5,
    ),
    historyWindow,
    songCount: clamp(
      readNumber(raw, "defaultSongCount", DEFAULT_MUSIC_SETTINGS.songCount),
      SONG_COUNT_MIN,
      SONG_COUNT_MAX,
    ),
    simpleMode: readBoolean(raw, "simpleMode", DEFAULT_MUSIC_SETTINGS.simpleMode),
    autoGenImage: readBoolean(raw, "autoGenImage", DEFAULT_MUSIC_SETTINGS.autoGenImage),
    autoGSuno: readBoolean(raw, "autoGSuno", DEFAULT_MUSIC_SETTINGS.autoGSuno),
    autoVideoAfterSuno: readBoolean(
      raw,
      "autoVideoAfterSuno",
      DEFAULT_MUSIC_SETTINGS.autoVideoAfterSuno,
    ),
    autoMergeAfterVideo: readBoolean(
      raw,
      "autoMergeAfterVideo",
      DEFAULT_MUSIC_SETTINGS.autoMergeAfterVideo,
    ),
    autoReelAfterVideo: readBoolean(
      raw,
      "autoReelAfterVideo",
      DEFAULT_MUSIC_SETTINGS.autoReelAfterVideo,
    ),
    autoUploadYouTube: readBoolean(
      raw,
      "autoUploadYouTube",
      DEFAULT_MUSIC_SETTINGS.autoUploadYouTube,
    ),
    polishStrength: clamp(
      readNumber(raw, "lyricsPolishStrength", DEFAULT_MUSIC_SETTINGS.polishStrength),
      0,
      100,
    ),
    shuffleStructure: readBoolean(
      raw,
      "shuffleStructure",
      DEFAULT_MUSIC_SETTINGS.shuffleStructure,
    ),
    shuffleMood: readBoolean(raw, "shuffleMood", DEFAULT_MUSIC_SETTINGS.shuffleMood),
    skipExistingBatches: readBoolean(
      raw,
      "skipExistingBatches",
      DEFAULT_MUSIC_SETTINGS.skipExistingBatches,
    ),
    primaryProfileIds: readStringArray(raw, "primaryProfileIds"),
    secondaryProfileIds: readStringArray(raw, "secondaryProfileIds"),
  };
}

export function musicSettingsPatch(settings: MusicSettings): Record<string, unknown> {
  return {
    language: settings.language,
    secondaryLanguage: settings.secondaryLanguage,
    creativity: settings.creativity,
    uniqueOpening: settings.uniqueOpening,
    shuffleStructure: settings.shuffleStructure,
    shuffleMood: settings.shuffleMood,
    useContentPools: settings.useContentPools,
    strictLevel: settings.strictLevel,
    uniquenessHistoryWindow: settings.historyWindow,
    defaultSongCount: settings.songCount,
    simpleMode: settings.simpleMode,
    autoGenImage: settings.autoGenImage,
    autoGSuno: settings.autoGSuno,
    autoVideoAfterSuno: settings.autoVideoAfterSuno,
    autoMergeAfterVideo: settings.autoMergeAfterVideo,
    autoReelAfterVideo: settings.autoReelAfterVideo,
    autoUploadYouTube: settings.autoUploadYouTube,
    skipExistingBatches: settings.skipExistingBatches,
    lyricsPolishStrength: settings.polishStrength,
    primaryProfileIds: settings.primaryProfileIds,
    secondaryProfileIds: settings.secondaryProfileIds,
  };
}

/** Stable string used to suppress a re-save when nothing actually changed. */
export function musicSettingsSnapshot(settings: MusicSettings): string {
  const patch = musicSettingsPatch(settings);
  const keys = Object.keys(patch).sort();
  return JSON.stringify(Object.fromEntries(keys.map((key) => [key, patch[key]])));
}

export function saveStatusLabel(status: "idle" | "saving" | "saved" | "error"): string {
  if (status === "saving") return "Saving...";
  if (status === "saved") return "Saved";
  if (status === "error") return "Unable to save";
  return "Autosave on";
}

export function imageSourceMode(settings: SettingsRecord | null | undefined): "ai" | "manual" {
  return String(settings?.imageSourceMode ?? "").trim().toLowerCase() === "manual"
    ? "manual"
    : "ai";
}

export function manualOutputBase(settings: SettingsRecord | null | undefined): string {
  const suno = String(settings?.sunoOutputDir ?? "").trim();
  if (suno) return suno;
  return String(settings?.downloadsDir ?? "").trim();
}
