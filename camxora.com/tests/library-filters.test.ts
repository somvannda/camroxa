import { describe, expect, it } from "vitest";

import {
  LIBRARY_FILTERS,
  matchesLibraryFilters,
  type LibraryFilterRow,
} from "@/lib/library-filters";

function row(overrides: Partial<LibraryFilterRow> = {}): LibraryFilterRow {
  return {
    liked: false,
    disliked: false,
    ready: true,
    duration: 180,
    instrumental: false,
    ...overrides,
  };
}

describe("matchesLibraryFilters", () => {
  it("shows everything when nothing is active", () => {
    expect(matchesLibraryFilters(row(), [])).toBe(true);
    expect(matchesLibraryFilters(row({ disliked: true }), [])).toBe(true);
  });

  it("narrows by like state", () => {
    expect(matchesLibraryFilters(row({ liked: true }), ["liked"])).toBe(true);
    expect(matchesLibraryFilters(row(), ["liked"])).toBe(false);
    expect(matchesLibraryFilters(row({ disliked: true }), ["disliked"])).toBe(true);
    expect(matchesLibraryFilters(row({ disliked: true }), ["hideDisliked"])).toBe(false);
  });

  it("requires playable audio for the ready filter", () => {
    expect(matchesLibraryFilters(row({ ready: false }), ["downloads"])).toBe(false);
    expect(matchesLibraryFilters(row({ ready: true }), ["downloads"])).toBe(true);
  });

  it("treats a preview-length clip as not a full song", () => {
    expect(matchesLibraryFilters(row({ duration: 30 }), ["full"])).toBe(false);
    expect(matchesLibraryFilters(row({ duration: 180 }), ["full"])).toBe(true);
    // Unknown length is not excluded: the corpus sometimes lacks a duration.
    expect(matchesLibraryFilters(row({ duration: 0 }), ["full"])).toBe(true);
  });

  it("separates vocals from instrumentals", () => {
    expect(matchesLibraryFilters(row({ instrumental: false }), ["voice"])).toBe(true);
    expect(matchesLibraryFilters(row({ instrumental: true }), ["voice"])).toBe(false);
    expect(matchesLibraryFilters(row({ instrumental: true }), ["instrumental"])).toBe(true);
    expect(matchesLibraryFilters(row({ instrumental: false }), ["instrumental"])).toBe(false);
  });

  it("requires every active filter to pass", () => {
    const filters = ["liked", "full"] as const;
    expect(matchesLibraryFilters(row({ liked: true, duration: 200 }), filters)).toBe(true);
    expect(matchesLibraryFilters(row({ liked: true, duration: 30 }), filters)).toBe(false);
    expect(matchesLibraryFilters(row({ liked: false, duration: 200 }), filters)).toBe(false);
  });
});

describe("LIBRARY_FILTERS", () => {
  it("keeps the data-blocked filters visible with a reason", () => {
    const blocked = LIBRARY_FILTERS.filter((filter) => filter.reason);
    expect(blocked.map((filter) => filter.id)).toEqual([
      "public",
      "private",
      "uploads",
      "cover",
      "hideStems",
    ]);
    for (const filter of blocked) {
      expect(filter.reason?.length).toBeGreaterThan(10);
    }
  });

  it("leaves the data-backed filters live", () => {
    const live = LIBRARY_FILTERS.filter((filter) => !filter.reason).map((filter) => filter.id);
    expect(live).toEqual([
      "liked",
      "disliked",
      "full",
      "voice",
      "instrumental",
      "downloads",
      "hideDisliked",
    ]);
  });
});
