import { describe, expect, it } from "vitest";

import type { WebMusicGeneration } from "@/lib/library-api";
import { initialOf, primaryClip, songTags } from "@/components/studio/StudioLibrary";

function song(overrides: Partial<WebMusicGeneration> = {}): WebMusicGeneration {
  return {
    id: "s1",
    title: "Song",
    style: "downtempo",
    status: "success",
    clips: [],
    ...overrides,
  } as WebMusicGeneration;
}

describe("primaryClip", () => {
  it("prefers a playable variant and falls back to the first clip", () => {
    const playable = { variant: "alt", audio_url: null };
    const ready = { variant: "ok", audio_url: "https://example.test/a.mp3" };
    expect(primaryClip(song({ clips: [playable, ready] }))).toBe(ready);
    expect(primaryClip(song({ clips: [playable] }))).toBe(playable);
    expect(primaryClip(song({ clips: [] }))).toBeNull();
  });
});

describe("songTags", () => {
  it("uses model, short label and length", () => {
    expect(
      songTags(
        song({
          model_label: "V6",
          clips: [{ variant: "alt", label: "Cover", duration_seconds: 127, audio_url: "u" }],
        })
      )
    ).toEqual(["V6", "Cover", "2:07"]);
  });

  it("falls back to the variant when a label is too long to fit the strip", () => {
    expect(
      songTags(
        song({
          model_label: "V6 PRO",
          clips: [
            {
              variant: "ok",
              label: "SEED DEMO LOOP · VERSION 1",
              audio_url: "u",
              duration_seconds: 4,
            },
          ],
        })
      )
    ).toEqual(["V6 PRO", "ok", "0:04"]);
  });

  it("omits pieces the clip does not have", () => {
    expect(songTags(song({ clips: [{ variant: "ok" }] }))).toEqual(["ok"]);
    expect(songTags(song())).toEqual([]);
  });
});

describe("initialOf", () => {
  it("uses the first letter or a placeholder", () => {
    expect(initialOf("Sunlit")).toBe("S");
    expect(initialOf("  ")).toBe("?");
    expect(initialOf(null)).toBe("?");
  });
});
