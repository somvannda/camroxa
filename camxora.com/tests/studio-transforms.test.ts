import { describe, expect, it } from "vitest";

import {
  extendedClipStart,
  healClipEdits,
  resultAudioUrl,
  resultDuration,
  withTransformTake,
} from "@/lib/studio-transforms";

describe("resultAudioUrl", () => {
  it("prefers the durable URL and falls back to the provider one", () => {
    expect(resultAudioUrl({ durable_url: "d", audio_url: "a" })).toBe("d");
    expect(resultAudioUrl({ durableUrl: "du", audio_url: "a" })).toBe("du");
    expect(resultAudioUrl({ audio_url: "a" })).toBe("a");
    expect(resultAudioUrl({})).toBeNull();
  });
});

describe("resultDuration", () => {
  it("reads either duration field and falls back", () => {
    expect(resultDuration({ duration_seconds: 12 })).toBe(12);
    expect(resultDuration({ duration: 9 })).toBe(9);
    expect(resultDuration({ duration_seconds: 0 }, 5)).toBe(5);
    expect(resultDuration({}, 4)).toBe(4);
  });
});

describe("withTransformTake", () => {
  const clip = {
    id: "clip-1",
    duration: 8,
    audioUrl: "old.wav",
    takes: [
      { id: "c1-t0", title: "Take 1", audioUrl: "old.wav", active: true },
      { id: "c1-t1", title: "Take 2", audioUrl: "older.wav", active: false },
    ],
  };

  it("adds the result as the active take and follows it for audio", () => {
    const next = withTransformTake(clip, "Cover 1", { audio_url: "cover.wav" }, "s1");

    expect(next.takes).toHaveLength(3);
    expect(next.takes?.[0]).toMatchObject({
      id: "clip-1-s1",
      title: "Cover 1",
      audioUrl: "cover.wav",
      active: true,
    });
    expect(next.audioUrl).toBe("cover.wav");
    // Prior takes are demoted, never dropped.
    expect(next.takes?.slice(1).every((take) => take.active === false)).toBe(true);
  });

  it("works when the clip had no takes yet", () => {
    const next = withTransformTake(
      { id: "clip-2", duration: 4, audioUrl: null },
      "Remaster",
      { durable_url: "remaster.wav", duration_seconds: 4.5 },
      "s2"
    );

    expect(next.takes).toHaveLength(1);
    expect(next.takes?.[0].duration).toBe(4.5);
    expect(next.audioUrl).toBe("remaster.wav");
  });

  it("keeps the clip audio when the result has no URL", () => {
    const next = withTransformTake(clip, "Cover 1", { title: "nothing" }, "s3");
    expect(next.audioUrl).toBe("old.wav");
    expect(next.takes?.[0].audioUrl).toBeNull();
  });
});

describe("healClipEdits", () => {
  it("restores the pre-transform audio and clears the takes", () => {
    const transformed = withTransformTake(
      { id: "clip", audioUrl: "original.wav", duration: 8 },
      "Cover",
      { audio_url: "cover.wav", duration_seconds: 9 },
      "s1"
    );
    expect(transformed.sourceAudioUrl).toBe("original.wav");
    expect(transformed.sourceDuration).toBe(8);

    const healed = healClipEdits(transformed);
    expect(healed.audioUrl).toBe("original.wav");
    expect(healed.duration).toBe(8);
    expect(healed.takes).toEqual([]);
    expect(healed.sourceAudioUrl).toBeNull();
  });

  it("leaves an untouched clip unchanged", () => {
    const clip = { id: "clip", audioUrl: "a.wav", duration: 4 };
    expect(healClipEdits(clip)).toBe(clip);
  });
});

describe("extendedClipStart", () => {
  it("places the extension immediately after its source", () => {
    expect(extendedClipStart({ start: 4, duration: 8 })).toBe(12);
    expect(extendedClipStart({ start: 0, duration: 4 })).toBe(4);
    expect(extendedClipStart({})).toBe(0);
  });
});
