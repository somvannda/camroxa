/** Shared option lists for the Export rail and the save-template dialog. */

export const EXPORT_ENCODERS = [
  { value: "wasm", label: "WebAssembly · x264 (CPU)" },
  { value: "webcodecs", label: "WebCodecs · hardware (GPU)" },
] as const;

/**
 * Same presets and wording as the editor's own Export dialog, including the
 * 1:2 portrait preset.
 */
export const EXPORT_RESOLUTIONS: Array<{ value: string; label: string }> = [
  { value: "640x360", label: "640x360 (360p)" },
  { value: "854x480", label: "854x480 (480p)" },
  { value: "1280x720", label: "1280x720 (720p)" },
  { value: "1920x1080", label: "1920x1080 (1080p)" },
  { value: "2560x1440", label: "2560x1440 (1440p)" },
  { value: "3840x2160", label: "3840x2160 (4K)" },
  { value: "360x640", label: "360x640 (360p, Portrait)" },
  { value: "480x854", label: "480x854 (480p, Portrait)" },
  { value: "720x1280", label: "720x1280 (720p, Portrait)" },
  { value: "1080x1920", label: "1080x1920 (1080p, Portrait)" },
  { value: "1440x2560", label: "1440x2560 (1440p, Portrait)" },
  { value: "2160x3840", label: "2160x3840 (4K, Portrait)" },
  { value: "360x360", label: "360x360 (360p, Square)" },
  { value: "480x480", label: "480x480 (480p, Square)" },
  { value: "720x720", label: "720x720 (720p, Square)" },
  { value: "1080x1080", label: "1080x1080 (1080p, Square)" },
  { value: "1440x1440", label: "1440x1440 (1440p, Square)" },
  { value: "2160x2160", label: "2160x2160 (4K, Square)" },
  { value: "1080x1350", label: "1080x1350 (Portrait)" },
  { value: "1080x2160", label: "1080x2160 (1:2)" },
];

export const EXPORT_FRAME_RATES = [24, 30, 60] as const;

export const EXPORT_FORMATS: Array<{ value: "h264" | "vp8" | "vp9"; label: string }> = [
  { value: "h264", label: "H.264 · MP4" },
  { value: "vp9", label: "VP9 · WebM" },
  { value: "vp8", label: "VP8 · WebM" },
];

export const EXPORT_PRESETS = [
  "ultrafast",
  "superfast",
  "veryfast",
  "faster",
  "fast",
  "medium",
  "slow",
  "slower",
  "veryslow",
] as const;

export const EXPORT_PROFILES = ["baseline", "main", "high"] as const;

/** `1920x1080` for a known resolution, otherwise `custom`. */
export function resolutionValue(width: number, height: number): string {
  const value = `${width}x${height}`;
  return EXPORT_RESOLUTIONS.some((option) => option.value === value) ? value : "custom";
}
