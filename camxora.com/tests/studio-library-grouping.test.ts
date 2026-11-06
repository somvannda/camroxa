import { describe, expect, it } from "vitest";

import { dayLabel, groupByDay } from "@/lib/studio-library-grouping";

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
