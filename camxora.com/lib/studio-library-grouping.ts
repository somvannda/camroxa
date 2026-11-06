/**
 * Library song grouping (spec §19.2): the reference's level-2 list is
 * "reverse-chronological, grouped by date header (`Yesterday`, `Oct 24, 2026`)".
 *
 * Pure so the labels can be tested without pinning the clock in a component test.
 */

export type DatedItem = { created_at?: string | null };

export type SongGroup<T> = { label: string; items: T[] };

function startOfDay(date: Date): number {
  return new Date(date.getFullYear(), date.getMonth(), date.getDate()).getTime();
}

/** "Today" / "Yesterday" / a locale date; unknown dates fall into "Earlier". */
export function dayLabel(iso: string | null | undefined, now: Date = new Date()): string {
  if (!iso) return "Earlier";
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return "Earlier";
  const day = startOfDay(date);
  const today = startOfDay(now);
  const dayMs = 86_400_000;
  if (day === today) return "Today";
  if (day === today - dayMs) return "Yesterday";
  if (day > today) return "Today";
  return date.toLocaleDateString(undefined, { month: "short", day: "numeric", year: "numeric" });
}

/**
 * Relative age for the level-1 Studio Projects rows (§19.1): the reference labels each
 * project "4m ago" / "1h, 41m ago", not with its tempo.
 */
export function relativeAge(iso: string | null | undefined, now: Date = new Date()): string {
  if (!iso) return "";
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return "";
  const minutes = Math.floor((now.getTime() - date.getTime()) / 60_000);
  if (minutes < 1) return "just now";
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) {
    const rest = minutes % 60;
    return rest > 0 ? `${hours}h, ${rest}m ago` : `${hours}h ago`;
  }
  const days = Math.floor(hours / 24);
  if (days < 7) return `${days}d ago`;
  return date.toLocaleDateString(undefined, { month: "short", day: "numeric" });
}

/**
 * Group items in the order they arrive (the API returns newest first). Groups keep the
 * first-seen order; an item without a date goes last.
 */
export function groupByDay<T extends DatedItem>(items: T[], now: Date = new Date()): SongGroup<T>[] {
  const groups = new Map<string, T[]>();
  for (const item of items) {
    const label = dayLabel(item.created_at, now);
    const list = groups.get(label);
    if (list) list.push(item);
    else groups.set(label, [item]);
  }
  const entries = [...groups.entries()];
  entries.sort(([a], [b]) => {
    if (a === "Earlier") return 1;
    if (b === "Earlier") return -1;
    return 0;
  });
  return entries.map(([label, group]) => ({ label, items: group }));
}
