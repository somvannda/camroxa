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
