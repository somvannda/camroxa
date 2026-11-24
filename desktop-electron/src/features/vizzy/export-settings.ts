import type { VizzyExportSettingsInput } from "../../../electron/shared/types";

/** Reference default: bitrate tracks the chosen height. */
export function defaultExportBitrate(height: number): number {
  if (height <= 360) return 5;
  if (height <= 480) return 5;
  if (height <= 720) return 15;
  if (height <= 1080) return 25;
  if (height <= 1440) return 50;
  if (height <= 2160) return 75;
  return 16;
}

/** Frame rates the Export rail offers; anything else falls back to 30. */
export function defaultExportFps(fps: number | undefined): 24 | 30 | 60 {
  return fps === 24 || fps === 60 ? fps : 30;
}

/**
 * The settings the Export rail starts from. Save-as-template stores them only
 * when the user opts in, so a pipeline render can reuse the same resolution,
 * frame rate and encoder quality.
 */
export function defaultExportSettings(project: {
  width: number;
  height: number;
  fps?: number;
  duration: number;
}): VizzyExportSettingsInput {
  const width = project.width || 1920;
  const height = project.height || 1080;
  return {
    width,
    height,
    fps: defaultExportFps(project.fps),
    format: "mp4",
    codec: "h264",
    engine: "wasm",
    bitrate: defaultExportBitrate(height),
    crf: 20,
    preset: "veryfast",
    profile: "high",
    audioBitrate: 192,
    start: 0,
    end: project.duration > 0 ? Number(project.duration.toFixed(2)) : undefined,
  };
}

export interface ExportSettingRow {
  label: string;
  value: string;
}

/**
 * The exact render profile stored in `pipeline.json`, as label/value pairs for
 * the Save-as-template dialog. Start/end are intentionally not listed: pipeline
 * renders always follow the song, never a saved trim.
 */
export function exportSettingRows(settings: VizzyExportSettingsInput): ExportSettingRow[] {
  const width = settings.width ?? 1920;
  const height = settings.height ?? 1080;
  const codec = settings.codec === "vp8" ? "VP8" : settings.codec === "vp9" ? "VP9" : "H.264";
  const container =
    settings.format === "webm" || codec !== "H.264" ? "WebM" : "MP4";
  const engine = settings.engine === "webcodecs" ? "WebCodecs" : "WebAssembly (x264)";
  const bitrate = Number(settings.bitrate) || 0;
  const crf = settings.crf ?? 20;
  const audio = settings.audioBitrate ?? 192;
  const rows: ExportSettingRow[] = [
    { label: "Resolution", value: `${width}×${height}` },
    { label: "Frame rate", value: `${settings.fps ?? 30} fps` },
    { label: "Encoder", value: engine },
    { label: "Format", value: `${codec} · ${container}` },
    {
      label: "Quality",
      value: bitrate > 0 ? `${bitrate} Mbps · CRF ${crf}` : `CRF ${crf}`,
    },
    { label: "Audio", value: `${audio} kbps` },
  ];
  if (codec === "H.264") {
    rows.push({
      label: "x264",
      value: `${settings.preset || "veryfast"} · ${settings.profile || "high"}`,
    });
  }
  rows.push({ label: "Trim", value: "Follows each song" });
  return rows;
}
