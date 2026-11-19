import { describe, expect, it } from "vitest";
import {
  clipFileName,
  formatDuration,
  generationIsFailed,
  generationIsReady,
  generationStatusLabel,
  type SimpleGeneration,
} from "../../src/features/music/simple-mode";

function generation(patch: Partial<SimpleGeneration> = {}): SimpleGeneration {
  return {
    id: "task-1",
    title: "Night Drive",
    lyrics: "",
    style: "",
    model: "V6",
    model_label: "V6 Pro",
    instrumental: false,
    status: "queued",
    clips: [],
    ...patch,
  };
}

describe("simple mode generation helpers", () => {
  it("treats a success status as ready", () => {
    expect(generationIsReady(generation({ status: "success" }))).toBe(true);
  });

  it("treats a ready clip as ready even while the status lags", () => {
    const item = generation({
      status: "processing",
      clips: [
        {
          variant: "ok",
          label: "Primary",
          audio_url: "/audio",
          download_url: "/download",
          ready: true,
        },
      ],
    });
    expect(generationIsReady(item)).toBe(true);
  });

  it("does not call a queued generation ready or failed", () => {
    const item = generation();
    expect(generationIsReady(item)).toBe(false);
    expect(generationIsFailed(item)).toBe(false);
    expect(generationStatusLabel(item)).toBe("Queued");
  });

  it("reports failures", () => {
    const item = generation({ status: "failed", error_message: "Suno rejected" });
    expect(generationIsFailed(item)).toBe(true);
    expect(generationStatusLabel(item)).toBe("Failed");
  });

  it("formats durations", () => {
    expect(formatDuration(null)).toBe("");
    expect(formatDuration(0)).toBe("");
    expect(formatDuration(65.4)).toBe("1:05");
    expect(formatDuration(180)).toBe("3:00");
  });

  it("builds a safe clip filename", () => {
    expect(clipFileName(generation({ title: "A/B: Test?" }), "ok", "mp3")).toBe(
      "AB Test (primary).mp3",
    );
    expect(clipFileName(generation({ title: "  " }), "alt", "wav")).toBe("song (alt).wav");
  });
});
