import { describe, expect, it } from "vitest";
import {
  defaultExportBitrate,
  defaultExportFps,
  defaultExportSettings,
  exportSettingRows,
} from "../../src/features/vizzy/export-settings";
import { formatExportSettings } from "../../src/features/vizzy/vizzy-format";

describe("export defaults", () => {
  it("only offers the frame rates the rail lists", () => {
    expect(defaultExportFps(24)).toBe(24);
    expect(defaultExportFps(30)).toBe(30);
    expect(defaultExportFps(60)).toBe(60);
    expect(defaultExportFps(25)).toBe(30);
    expect(defaultExportFps(undefined)).toBe(30);
  });

  it("follows the project output instead of a fixed 1080p/30 preset", () => {
    const settings = defaultExportSettings({ width: 1080, height: 1920, fps: 60, duration: 180 });
    expect(settings).toMatchObject({
      width: 1080,
      height: 1920,
      fps: 60,
      codec: "h264",
      format: "mp4",
      engine: "wasm",
      bitrate: 75,
      crf: 20,
      preset: "veryfast",
      profile: "high",
      audioBitrate: 192,
      start: 0,
      end: 180,
    });
    expect(defaultExportBitrate(1080)).toBe(25);
    expect(defaultExportBitrate(720)).toBe(15);
  });

  it("formats a one-line encoder summary for the save dialog", () => {
    expect(
      formatExportSettings({ width: 1920, height: 1080, fps: 30, codec: "h264", engine: "wasm" }),
    ).toBe("1920×1080 · 30 fps · H.264 MP4 · WebAssembly");
    expect(formatExportSettings({ width: 1080, height: 1920, fps: 60, codec: "vp9" })).toBe(
      "1080×1920 · 60 fps · VP9 WebM · WebAssembly",
    );
  });

  it("lists the exact render profile the template would store", () => {
    const rows = exportSettingRows({
      width: 1920,
      height: 1080,
      fps: 30,
      format: "mp4",
      codec: "h264",
      engine: "wasm",
      bitrate: 25,
      crf: 20,
      preset: "veryfast",
      profile: "high",
      audioBitrate: 192,
      start: 0,
      end: 12,
    });
    expect(rows).toEqual([
      { label: "Resolution", value: "1920×1080" },
      { label: "Frame rate", value: "30 fps" },
      { label: "Encoder", value: "WebAssembly (x264)" },
      { label: "Format", value: "H.264 · MP4" },
      { label: "Quality", value: "25 Mbps · CRF 20" },
      { label: "Audio", value: "192 kbps" },
      { label: "x264", value: "veryfast · high" },
      { label: "Trim", value: "Follows each song" },
    ]);
    // A trim in the rail is never stored, and VP9 has no x264 preset row.
    expect(rows.some((row) => row.label === "Trim")).toBe(true);
    const vp9 = exportSettingRows({ codec: "vp9", bitrate: 0, crf: 32 });
    expect(vp9.some((row) => row.label === "x264")).toBe(false);
    expect(vp9.find((row) => row.label === "Format")?.value).toBe("VP9 · WebM");
    expect(vp9.find((row) => row.label === "Quality")?.value).toBe("CRF 32");
  });
});
