/** Small display helpers shared by the export menu and the renders panel. */

export function formatBytes(bytes: number): string {
  if (!Number.isFinite(bytes) || bytes <= 0) return "0 B";
  const units = ["B", "KB", "MB", "GB"];
  let value = bytes;
  let unit = 0;
  while (value >= 1024 && unit < units.length - 1) {
    value /= 1024;
    unit += 1;
  }
  const digits = value >= 100 || unit === 0 ? 0 : 1;
  return `${value.toFixed(digits)} ${units[unit]}`;
}

export function formatDuration(seconds: number): string {
  if (!Number.isFinite(seconds) || seconds <= 0) return "0:00";
  const whole = Math.round(seconds);
  return `${Math.floor(whole / 60)}:${String(whole % 60).padStart(2, "0")}`;
}

export function formatRenderDate(mtimeMs: number): string {
  if (!Number.isFinite(mtimeMs) || mtimeMs <= 0) return "";
  return new Intl.DateTimeFormat("en-US", {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  }).format(new Date(mtimeMs));
}

/** One-line encoder summary: `1920×1080 · 30 fps · H.264 MP4 · WebAssembly`. */
export function formatExportSettings(settings: {
  width?: number;
  height?: number;
  fps?: number;
  format?: "mp4" | "webm";
  codec?: "h264" | "vp8" | "vp9";
  engine?: "wasm" | "webcodecs";
}): string {
  const width = settings.width ?? 1920;
  const height = settings.height ?? 1080;
  const fps = settings.fps ?? 30;
  const codec = settings.codec === "vp8" ? "VP8" : settings.codec === "vp9" ? "VP9" : "H.264";
  const format = settings.format === "webm" || settings.codec === "vp8" || settings.codec === "vp9"
    ? "WebM"
    : "MP4";
  const engine = settings.engine === "webcodecs" ? "WebCodecs" : "WebAssembly";
  return `${width}×${height} · ${fps} fps · ${codec} ${format} · ${engine}`;
}
