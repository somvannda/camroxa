/**
 * Track groups A–D (reference ARR-027).
 *
 * A group is a mix multiplier over its member tracks plus a collapse state; membership
 * lives on the track (`groupId`), the group itself only carries its level. Playback and
 * export apply the multiplier before the track fader, so a group is a real submix rather
 * than a label.
 */

import { TRACK_GROUPS, type StudioTrack, type TrackGroupId } from "@/lib/studio-tracks";

export type GroupMix = Partial<Record<TrackGroupId, number>>;

export const DEFAULT_GROUP_MIX: GroupMix = {};

function clamp(value: unknown, fallback: number): number {
  return typeof value === "number" && Number.isFinite(value)
    ? Math.max(0, Math.min(100, value))
    : fallback;
}

/** Read `data.groups`, ignoring unknown ids and clamping levels to 0–100. */
export function sanitizeGroups(input: unknown): GroupMix {
  if (!input || typeof input !== "object") return {};
  const source = input as Record<string, unknown>;
  const next: GroupMix = {};
  for (const group of TRACK_GROUPS) {
    if (source[group] === undefined) continue;
    next[group] = clamp(source[group], 100);
  }
  return next;
}

/** Multiplier (0–1) a track's fader should receive from its group. */
export function groupGain(groups: GroupMix, track: Pick<StudioTrack, "groupId">): number {
  const id = track.groupId;
  if (!id) return 1;
  return clamp(groups[id] ?? 100, 100) === 100 ? 1 : clamp(groups[id] ?? 100, 100) / 100;
}

/** Groups that at least one visible track belongs to, in A–D order. */
export function groupsInUse(tracks: StudioTrack[]): Array<{ id: TrackGroupId; count: number }> {
  return TRACK_GROUPS.map((id) => ({
    id,
    count: tracks.filter((track) => track.groupId === id).length,
  })).filter((group) => group.count > 0);
}
