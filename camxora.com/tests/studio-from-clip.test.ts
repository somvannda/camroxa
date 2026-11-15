import { describe, expect, it } from "vitest";

import type { WebMusicGeneration } from "@/lib/library-api";
import { projectFromSong } from "@/lib/studio-from-clip";

const SONG: WebMusicGeneration = {
  id: "gen-123",
  title: "Night Drive",
  style: "synthwave",
  status: "completed",
  clips: [
    {
      variant: "ok",
      label: "Version 1",
      title: "Night Drive",
      audio_url: "https://cdn.example/night-drive.mp3",
      duration_seconds: 132,
      ready: true,
    },
    {
      variant: "alt",
      label: "Version 2",
      title: "Night Drive (alt)",
      audio_url: "https://cdn.example/night-drive-alt.mp3",
      duration_seconds: 131,
      ready: true,
    },
  ],
};

describe("projectFromSong", () => {
  it("builds a one-track project that references the chosen version", () => {
    const draft = projectFromSong(SONG, "alt");
    expect(draft).not.toBeNull();
    if (!draft) return;
    expect(draft.title).toBe("Night Drive (alt)");
    expect(draft.bpm).toBe(120);
    expect(draft.time_signature).toBe("4/4");
    const tracks = draft.data.tracks as Array<Record<string, unknown>>;
    const lanes = draft.data.lanes as Array<Record<string, unknown>>;
    expect(tracks).toHaveLength(1);
    expect(tracks[0].clipIds).toEqual([lanes[0].id]);
    expect(lanes[0]).toMatchObject({
      title: "Night Drive (alt)",
      start: 0,
      duration: 131,
      audioUrl: "https://cdn.example/night-drive-alt.mp3",
      songId: "gen-123",
      songVariant: "alt",
    });
  });

  it("falls back to any version with audio when the requested one is gone", () => {
    const draft = projectFromSong(SONG, "alt");
    expect(draft).not.toBeNull();
    const withoutAlt: WebMusicGeneration = {
      ...SONG,
      clips: [{ ...SONG.clips[0], variant: "ok" }],
    };
    const fallback = projectFromSong(withoutAlt, "alt");
    expect(fallback).not.toBeNull();
    const lanes = fallback?.data.lanes as Array<Record<string, unknown>>;
    expect(lanes[0].songVariant).toBe("ok");
  });

  it("returns null when no version has audio yet", () => {
    expect(
      projectFromSong({ ...SONG, clips: [{ ...SONG.clips[0], audio_url: null }] })
    ).toBeNull();
  });
});
