/** Shared option lists for the Export rail and the save-template dialog. */

export const EXPORT_RESOLUTIONS: Array<{ value: string; label: string }> = [
  { value: "640x360", label: "640×360 (360p)" },
  { value: "854x480", label: "854×480 (480p)" },
  { value: "1280x720", label: "1280×720 (720p)" },
  { value: "1920x1080", label: "1920×1080 (1080p)" },
  { value: "2560x1440", label: "2560×1440 (1440p)" },
  { value: "3840x2160", label: "3840×2160 (4K)" },
  { value: "360x640", label: "360×640 (Portrait 360p)" },
  { value: "480x854", label: "480×854 (Portrait 480p)" },
  { value: "720x1280", label: "720×1280 (Portrait 720p)" },
  { value: "1080x1920", label: "1080×1920 (Portrait 1080p)" },
  { value: "1440x2560", label: "1440×2560 (Portrait 1440p)" },
  { value: "2160x3840", label: "2160×3840 (Portrait 4K)" },
  { value: "360x360", label: "360×360 (Square 360p)" },
  { value: "480x480", label: "480×480 (Square 480p)" },
  { value: "720x720", label: "720×720 (Square 720p)" },
  { value: "1080x1080", label: "1080×1080 (Square 1080p)" },
  { value: "1440x1440", label: "1440×1440 (Square 1440p)" },
  { value: "2160x2160", label: "2160×2160 (Square 4K)" },
  { value: "1080x1350", label: "1080×1350 (Portrait)" },
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
