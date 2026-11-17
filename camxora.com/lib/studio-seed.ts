import type { WebMusicClip, WebMusicGeneration } from "@/lib/library-api";
import type { StudioProjectData } from "@/lib/studio-api";
import { colorForTrackName } from "@/lib/studio-tracks";

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

/**
 * The loop we own, shipped in `public/` — 4 s, mono, 22.05 kHz. The demo tile plays
 * this file directly (no provider call, no generated audio).
 */
export const DEMO_LOOP_URL = "/seed/demo-loop.wav";
export const DEMO_PROJECT_TITLE = "Drum & Bass Demo";
/** The loop's real length in seconds (read off the WAV header). */
const DEMO_LOOP_SECONDS = 4;
/** The capture's demo project runs at 174 BPM (S17). */
const DEMO_BPM = 174;
const DEMO_TRACK_ID = "track-demo-loop";
const DEMO_CLIP_ID = "clip-demo-loop";

/** The captured master rack (S26/S48) is not empty: three real bus entries. */
function masterRack(): Array<{ id: string; type: string; amount: number }> {
  return [
    { id: "master-compressor", type: "compressor", amount: 0.3 },
    { id: "master-eq", type: "eq", amount: 0.2 },
    { id: "master-eq-2", type: "eq", amount: 0.15 },
  ];
}

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
    data: {
      lanes: [lane],
      // The captured master rack is not empty (S26/S48): a song opened from the library
      // starts with a real chain instead of an empty dock. Types are the three the master
      // bus actually implements.
      masterChain: masterRack(),
    } as StudioProjectData,
  };
}

/**
 * Pure: the "Drum & Bass Demo" start-overlay tile (S03/S06).
 *
 * The reference opens a bundled multi-track project; we do not ship that arrangement, so
 * the tile seeds one we own instead: our loop as an audio clip on one Audio Track at bar
 * one, already audible (`clip.audioUrl` is what the editor plays). No Suno content and no
 * provider call — the document is built here and created through `createStudioProject`.
 */
export function buildDemoProject(): SeededProject {
  return {
    title: DEMO_PROJECT_TITLE,
    bpm: DEMO_BPM,
    data: {
      lanes: [
        {
          id: DEMO_CLIP_ID,
          title: DEMO_PROJECT_TITLE,
          start: 0,
          duration: DEMO_LOOP_SECONDS,
          volume: 1,
          pan: 0,
          muted: false,
          solo: false,
          audioUrl: DEMO_LOOP_URL,
        },
      ],
      tracks: [
        {
          id: DEMO_TRACK_ID,
          name: "Drum & Bass Loop",
          color: colorForTrackName("Drum & Bass Loop"),
          index: 0,
          volume: 80,
          pan: 0,
          muted: false,
          solo: false,
          hidden: false,
          collapsed: false,
          groupId: null,
          chain: [],
          clipIds: [DEMO_CLIP_ID],
        },
      ],
      masterChain: masterRack(),
    } as StudioProjectData,
  };
}

/** The captured empty project (S05/S16) starts with one Audio Track, not zero. */
export function emptyProjectData(): StudioProjectData {
  return {
    lanes: [],
    tracks: [
      {
        id: "track-audio-1",
        name: "Audio Track",
        color: colorForTrackName("Audio Track"),
        index: 0,
        volume: 80,
        pan: 0,
        muted: false,
        solo: false,
        hidden: false,
        collapsed: false,
        chain: [],
        clipIds: [],
      },
    ],
  } as StudioProjectData;
}
