import { describe, expect, it } from "vitest";

import { dayLabel, groupByDay, relativeAge } from "@/lib/studio-library-grouping";

const NOW = new Date(2026, 10, 6, 12, 0, 0); // 6 Nov 2026, local time

describe("dayLabel", () => {
  it("names today and yesterday", () => {
    expect(dayLabel(new Date(2026, 10, 6, 9, 0, 0).toISOString(), NOW)).toBe("Today");
    expect(dayLabel(new Date(2026, 10, 5, 23, 0, 0).toISOString(), NOW)).toBe("Yesterday");
  });

  it("formats older dates and buckets missing ones", () => {
    const label = dayLabel(new Date(2026, 9, 24, 10, 0, 0).toISOString(), NOW);
    expect(label).toBe(
      new Date(2026, 9, 24).toLocaleDateString(undefined, {
        month: "short",
        day: "numeric",
        year: "numeric",
      })
    );
    expect(dayLabel(null, NOW)).toBe("Earlier");
    expect(dayLabel("not a date", NOW)).toBe("Earlier");
  });

  it("treats a future timestamp as today rather than inventing a label", () => {
    expect(dayLabel(new Date(2026, 10, 7, 9, 0, 0).toISOString(), NOW)).toBe("Today");
  });
});

describe("groupByDay", () => {
  it("keeps arrival order and groups by day", () => {
    const items = [
      { id: "a", created_at: new Date(2026, 10, 6, 10, 0, 0).toISOString() },
      { id: "b", created_at: new Date(2026, 10, 6, 8, 0, 0).toISOString() },
      { id: "c", created_at: new Date(2026, 10, 5, 8, 0, 0).toISOString() },
      { id: "d" },
    ];
    const groups = groupByDay(items, NOW);
    expect(groups.map((group) => group.label)).toEqual(["Today", "Yesterday", "Earlier"]);
    expect(groups[0].items.map((item) => item.id)).toEqual(["a", "b"]);
    expect(groups[2].items.map((item) => item.id)).toEqual(["d"]);
  });

  it("returns nothing for an empty list", () => {
    expect(groupByDay([], NOW)).toEqual([]);
  });
});

describe("relativeAge", () => {
  const at = (minutesAgo: number) =>
    new Date(NOW.getTime() - minutesAgo * 60_000).toISOString();

  it("matches the reference's project labels", () => {
    expect(relativeAge(at(0), NOW)).toBe("just now");
    expect(relativeAge(at(4), NOW)).toBe("4m ago");
    expect(relativeAge(at(14), NOW)).toBe("14m ago");
    expect(relativeAge(at(101), NOW)).toBe("1h, 41m ago");
    expect(relativeAge(at(120), NOW)).toBe("2h ago");
    expect(relativeAge(at(60 * 24 * 3), NOW)).toBe("3d ago");
    expect(relativeAge(at(60 * (24 * 5 + 9)), NOW)).toBe("5d, 9h ago");
  });

  it("falls back to a date for older work and blanks for missing dates", () => {
    const old = new Date(2026, 8, 24, 10, 0, 0).toISOString();
    expect(relativeAge(old, NOW)).toBe(
      new Date(old).toLocaleDateString(undefined, { month: "short", day: "numeric" })
    );
    expect(relativeAge(null, NOW)).toBe("");
    expect(relativeAge("not a date", NOW)).toBe("");
  });
});
