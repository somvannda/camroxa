/**
 * "Open in Studio" from a generated song.
 *
 * Suno's menu opens the song in the Studio; we mirror that by building a
 * one-track project document from the chosen version. The audio is referenced by
 * URL (`audioUrl` + `songId`), the same shape the Library uses when it drops a
 * song onto the timeline, so the editor can play it immediately.
 */

import type { WebMusicGeneration } from "@/lib/library-api";

export type SongProjectDraft = {
  title: string;
  bpm: number;
  time_signature: string;
  data: Record<string, unknown>;
};

function shortId(value: string): string {
  return value.replace(/[^a-zA-Z0-9]/g, "").slice(0, 10) || "song";
}

/** Build a Studio project from one generation version, or null when no audio is ready. */
export function projectFromSong(
  song: WebMusicGeneration,
  variant: "ok" | "alt" = "ok"
): SongProjectDraft | null {
  const clips = Array.isArray(song.clips) ? song.clips : [];
  const clip =
    clips.find((candidate) => candidate.variant === variant && candidate.audio_url) ??
    clips.find((candidate) => candidate.audio_url);
  if (!clip?.audio_url) return null;
  const title = (clip.title || song.title || "Song").trim().slice(0, 120) || "Song";
  const duration = Math.max(1, Number(clip.duration_seconds) || 8);
  const suffix = shortId(song.id);
  const trackId = `track-${suffix}`;
  const clipId = `clip-${suffix}`;
  return {
    title: title.slice(0, 120),
    bpm: 120,
    time_signature: "4/4",
    data: {
      tracks: [
        {
          id: trackId,
          name: title.slice(0, 40),
          index: 0,
          clipIds: [clipId],
        },
      ],
      lanes: [
        {
          id: clipId,
          title,
          start: 0,
          duration,
          volume: 1,
          pan: 0,
          audioUrl: clip.audio_url,
          songId: song.id,
          songVariant: clip.variant,
        },
      ],
    },
  };
}
