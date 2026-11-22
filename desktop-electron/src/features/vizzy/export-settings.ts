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

/**
 * The settings the Export rail starts from. Save-as-template stores them so a
 * pipeline render uses the same resolution, frame rate and encoder quality.
 */
export function defaultExportSettings(project: {
  width: number;
  height: number;
  duration: number;
}): VizzyExportSettingsInput {
  const width = project.width || 1920;
  const height = project.height || 1080;
  return {
    width,
    height,
    fps: 30,
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
