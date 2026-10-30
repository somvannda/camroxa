/**
 * Track model.
 *
 * The editor originally treated a clip as a track: `Clip` carried volume, pan,
 * mute/solo and the FX values. That cannot represent the reference, where a track
 * is a container that owns many clips, a plugin chain, automation and a take stack
 * (see docs/studio/SUNO_STUDIO_TECHNICAL_ARCHITECTURE.md §32).
 *
 * This module introduces the container without changing behaviour:
 * - `lanes` remains the source of clips (no duplicated clip data);
 * - a track holds `clipIds`, mix state and its plugin chain;
 * - `migrateLanesToTracks` turns a legacy document into one track per clip, which
 *   is exactly what the old model implied, so rendering is unaffected.
 *
 * Flipping rendering from `lanes` to `tracks` is a later, separate change.
 */

import type { PluginChainEntry } from "@/lib/studio-plugins";

export type StudioTrack = {
  id: string;
  name: string;
  color: string;
  /** Display order; tracks are rendered by ascending index. */
  index: number;
  volume: number;
  pan: number;
  muted: boolean;
  solo: boolean;
  /** Hidden tracks are excluded from the arrangement but keep state (`SHIFT H`). */
  hidden: boolean;
  /** Visual group A–D from the legacy model. */
  groupId: string | null;
  /** Ordered plugin chain; signal order. */
  chain: PluginChainEntry[];
  /** Ids of the clips that live on this track. */
  clipIds: string[];
};

/** The subset of a legacy clip that used to describe "a track". */
type LegacyClipLike = {
  id: string;
  title?: string;
  color?: string;
  volume?: number;
  pan?: number;
  muted?: boolean;
  solo?: boolean;
  groupId?: string | null;
};

/** Reference colour families: vocals magenta, bass blue, strings/violet, SFX orange, drums olive. */
export function colorForTrackName(name: string): string {
  const value = name.toLowerCase();
  if (/vocal|voice|sing|choir|harmon/.test(value)) return "#ec4899";
  if (/bass|sub|808/.test(value)) return "#2f7bf6";
  if (/string|piano|key|synth|pad|guitar|brass|horn|lead/.test(value)) return "#7c5cf0";
  if (/effect|sfx|alarm|crash|riser|impact|noise/.test(value)) return "#f97316";
  if (/drum|kit|hat|snare|kick|perc|tom|clap/.test(value)) return "#a3a327";
  return "#8b5cf6";
}

function num(value: unknown, fallback: number): number {
  return typeof value === "number" && Number.isFinite(value) ? value : fallback;
}

/**
 * Derive tracks from a legacy clip list.
 *
 * One track per clip, in clip order. Ids are deterministic (`track-<clipId>`) so a
 * document migrated twice produces the same result and diff-free saves.
 */
export function migrateLanesToTracks(lanes: LegacyClipLike[]): StudioTrack[] {
  return lanes.map((clip, index) => ({
    id: `track-${clip.id}`,
    name: clip.title || `Track ${index + 1}`,
    color: clip.color || colorForTrackName(clip.title || ""),
    index,
    volume: num(clip.volume, 80),
    pan: num(clip.pan, 0),
    muted: Boolean(clip.muted),
    solo: Boolean(clip.solo),
    hidden: false,
    groupId: clip.groupId ?? null,
    chain: [],
    clipIds: [clip.id],
  }));
}

/** Validate a persisted track list; unknown fields are dropped. */
export function sanitizeTracks(input: unknown): StudioTrack[] {
  if (!Array.isArray(input)) return [];
  const seen = new Set<string>();
  const out: StudioTrack[] = [];
  for (const raw of input) {
    if (!raw || typeof raw !== "object") continue;
    const candidate = raw as Partial<StudioTrack>;
    if (typeof candidate.id !== "string" || !candidate.id || seen.has(candidate.id)) continue;
    seen.add(candidate.id);
    const clipIds = Array.isArray(candidate.clipIds)
      ? candidate.clipIds.filter((id): id is string => typeof id === "string" && id.length > 0)
      : [];
    out.push({
      id: candidate.id,
      name: typeof candidate.name === "string" && candidate.name ? candidate.name : "Track",
      color: typeof candidate.color === "string" && candidate.color ? candidate.color : colorForTrackName(typeof candidate.name === "string" ? candidate.name : ""),
      index: num(candidate.index, out.length),
      volume: Math.min(100, Math.max(0, num(candidate.volume, 80))),
      pan: Math.min(100, Math.max(-100, num(candidate.pan, 0))),
      muted: Boolean(candidate.muted),
      solo: Boolean(candidate.solo),
      hidden: Boolean(candidate.hidden),
      groupId: typeof candidate.groupId === "string" ? candidate.groupId : null,
      chain: [], // chains are sanitised separately, by track id
      clipIds,
    });
  }
  return out.sort((a, b) => a.index - b.index);
}

/**
 * Keep the two representations consistent: every track references existing clips,
 * and every clip belongs to exactly one track.
 */
export function reconcileTracks(
  tracks: StudioTrack[],
  lanes: LegacyClipLike[]
): StudioTrack[] {
  const liveIds = new Set(lanes.map((clip) => clip.id));
  const claimed = new Set<string>();
  const next: StudioTrack[] = [];

  for (const track of tracks) {
    const clipIds = track.clipIds.filter((id) => liveIds.has(id) && !claimed.has(id));
    clipIds.forEach((id) => claimed.add(id));
    next.push({ ...track, clipIds, index: next.length });
  }

  const orphans = lanes.filter((clip) => !claimed.has(clip.id));
  if (orphans.length) {
    next.push(...migrateLanesToTracks(orphans).map((track, offset) => ({
      ...track,
      index: next.length + offset,
    })));
  }

  return next;
}

/** Track that owns a clip, or null when the document is inconsistent. */
export function trackIdForClip(tracks: StudioTrack[], clipId: string): string | null {
  return tracks.find((track) => track.clipIds.includes(clipId))?.id ?? null;
}
