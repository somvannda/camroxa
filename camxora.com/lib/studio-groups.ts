/**
 * Track groups and group mix.
 *
 * Groups are document records referenced by `StudioTrack.groupId`. A group's volume
 * scales the track fader, its mute silences the member tracks, and its solo wins over
 * track solo the same way the legacy mixer did: if any group is soloed, only tracks
 * in a soloed group are audible.
 */

export type StudioGroup = {
  id: string;
  name: string;
  color: string;
  volume: number;
  muted: boolean;
  solo: boolean;
};

const DEFAULT_COLORS = ["#38bdf8", "#a78bfa", "#f472b6", "#fb923c", "#4ade80"];

export function sanitizeGroups(input: unknown): StudioGroup[] {
  if (!Array.isArray(input)) return [];
  const seen = new Set<string>();
  const groups: StudioGroup[] = [];
  for (const raw of input) {
    if (!raw || typeof raw !== "object") continue;
    const value = raw as Record<string, unknown>;
    if (typeof value.id !== "string" || !value.id || seen.has(value.id)) continue;
    seen.add(value.id);
    const volume = Number(value.volume);
    groups.push({
      id: value.id,
      name: typeof value.name === "string" && value.name ? value.name.slice(0, 60) : "Group",
      color:
        typeof value.color === "string" && value.color
          ? value.color
          : DEFAULT_COLORS[groups.length % DEFAULT_COLORS.length],
      volume: Number.isFinite(volume) ? Math.min(100, Math.max(0, volume)) : 100,
      muted: Boolean(value.muted),
      solo: Boolean(value.solo),
    });
  }
  return groups;
}

export function groupFor(
  track: { groupId?: string | null },
  groups: StudioGroup[]
): StudioGroup | null {
  if (!track.groupId) return null;
  return groups.find((group) => group.id === track.groupId) ?? null;
}

export function effectiveTrackMix(
  track: {
    volume: number;
    muted: boolean;
    solo: boolean;
    groupId?: string | null;
  },
  groups: StudioGroup[],
  anySolo: boolean
): { volume: number; muted: boolean; solo: boolean } {
  const group = groupFor(track, groups);
  const anyGroupSolo = groups.some((item) => item.solo);
  const groupSolo = Boolean(group?.solo);
  return {
    volume: Math.max(0, Math.min(100, track.volume * ((group?.volume ?? 100) / 100))),
    muted: track.muted || Boolean(group?.muted) || (anyGroupSolo && !groupSolo),
    solo: anyGroupSolo ? groupSolo : track.solo,
  };
}
