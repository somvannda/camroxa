import { describe, expect, it } from "vitest";

import { buildSeedFromSong, isSeedable, pickSeedClip } from "@/lib/studio-seed";
import type { WebMusicGeneration } from "@/lib/library-api";

function song(overrides: Partial<WebMusicGeneration> = {}): WebMusicGeneration {
  return {
    id: "song-1",
    title: "Seed Demo Loop",
    style: "downtempo",
    status: "complete",
    clips: [
      { variant: "ok", title: "Version 1", audio_url: "", duration_seconds: null, ready: false },
      { variant: "alt", title: "Version 2", audio_url: "/audio/alt.wav", duration_seconds: 12, ready: true },
    ],
    ...overrides,
  } as WebMusicGeneration;
}

describe("pickSeedClip", () => {
  it("prefers a ready clip with audio over an unready one", () => {
    expect(pickSeedClip(song())?.variant).toBe("alt");
  });

  it("falls back to any clip that has audio", () => {
    const fallback = song({
      clips: [{ variant: "ok", audio_url: "/audio/ok.wav", ready: false }],
    });
    expect(pickSeedClip(fallback)?.variant).toBe("ok");
  });

  it("returns null when nothing is playable", () => {
    expect(pickSeedClip(song({ clips: [{ variant: "ok", audio_url: "" }] }))).toBeNull();
    expect(pickSeedClip(song({ clips: [] }))).toBeNull();
  });
});

describe("isSeedable", () => {
  it("accepts a playable song", () => {
    expect(isSeedable(song())).toBe(true);
  });

  it("rejects an errored song even if it has audio", () => {
    expect(isSeedable(song({ status: "error" }))).toBe(false);
  });
});

describe("buildSeedFromSong", () => {
  it("seeds one lane from the playable clip", () => {
    const seed = buildSeedFromSong(song());
    const lanes = (seed.data as { lanes: Array<Record<string, unknown>> }).lanes;
    expect(lanes).toHaveLength(1);
    expect(lanes[0]).toMatchObject({
      title: "Version 2",
      start: 0,
      duration: 12,
      audioUrl: "/audio/alt.wav",
    });
  });

  it("defaults the title and duration when the clip is thin", () => {
    const thin = song({
      title: "  ",
      clips: [{ variant: "ok", audio_url: "/a.wav", ready: true }],
    });
    const seed = buildSeedFromSong(thin);
    const lane = (seed.data as { lanes: Array<Record<string, unknown>> }).lanes[0];
    expect(seed.title).toBe("Untitled song");
    expect(lane.duration).toBe(120);
  });

  it("honours an explicit tempo", () => {
    expect(buildSeedFromSong(song(), { bpm: 140 }).bpm).toBe(140);
  });
});
