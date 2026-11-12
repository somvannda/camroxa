import type { WebMusicClip, WebMusicGeneration } from "@/lib/library-api";
import type { StudioProjectData } from "@/lib/studio-api";

/**
 * Seeding a Studio project from an existing song.
 *
 * Reference behaviour (spec §10, "Edit Your Song — Open a song from your library"):
 * picking a song opens a project that already contains that audio rather than an
 * empty arrangement. The editor plays `clip.audioUrl` (see StudioEditorShell), so a
 * seeded lane is audible immediately — no copy, no re-render.
 *
 * A generation carries one or more `clips` (versions); we seed with the first that
 * is ready and has audio.
 */

export type SeededProject = {
  title: string;
  bpm: number;
  data: StudioProjectData;
};

const DEFAULT_DURATION = 120;

function cleanTitle(value?: string | null): string {
  const trimmed = (value ?? "").trim();
  return trimmed.length > 0 ? trimmed : "Untitled song";
}

/** First playable version of a song, preferring clips marked ready. */
export function pickSeedClip(song: WebMusicGeneration): WebMusicClip | null {
  const clips = song.clips ?? [];
  return (
    clips.find((clip) => clip.ready && clip.audio_url) ??
    clips.find((clip) => Boolean(clip.audio_url)) ??
    null
  );
}

/** True when the song can actually be placed (has a playable version). */
export function isSeedable(song: WebMusicGeneration): boolean {
  return song.status !== "error" && pickSeedClip(song) !== null;
}

/**
 * Pure: takes a generation and returns the payload `createStudioProject` expects.
 * Free of React and fetch so it can be unit-tested once W5.1 lands.
 */
export function buildSeedFromSong(
  song: WebMusicGeneration,
  options: { bpm?: number } = {}
): SeededProject {
  const clip = pickSeedClip(song);
  const title = cleanTitle(clip?.title || song.title);
  const duration =
    typeof clip?.duration_seconds === "number" && clip.duration_seconds > 0
      ? clip.duration_seconds
      : DEFAULT_DURATION;

  const lane = {
    id: `lane-${song.id}`,
    title,
    start: 0,
    duration,
    volume: 1,
    pan: 0,
    muted: false,
    solo: false,
    audioUrl: clip?.audio_url ?? null,
  };

  return {
    title,
    bpm: options.bpm ?? 120,
    data: { lanes: [lane] } as StudioProjectData,
  };
}
