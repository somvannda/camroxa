import { describe, expect, it } from "vitest";

import { groupGain, groupsInUse, sanitizeGroups } from "@/lib/studio-groups";
import type { StudioTrack } from "@/lib/studio-tracks";

function track(overrides: Partial<StudioTrack> = {}): StudioTrack {
  return {
    id: "t1",
    name: "Track 1",
    color: "#8b5cf6",
    index: 0,
    volume: 80,
    pan: 0,
    muted: false,
    solo: false,
    hidden: false,
    collapsed: false,
    groupId: null,
    chain: [],
    clipIds: ["c1"],
    ...overrides,
  };
}

describe("sanitizeGroups", () => {
  it("keeps known groups, clamps levels and drops junk", () => {
    expect(sanitizeGroups({ A: 120, B: -4, C: 50, E: 10, x: "nope" })).toEqual({
      A: 100,
      B: 0,
      C: 50,
    });
  });

  it("returns an empty mix for junk input", () => {
    expect(sanitizeGroups(null)).toEqual({});
    expect(sanitizeGroups("nope")).toEqual({});
  });
});

describe("groupGain", () => {
  it("is unity for ungrouped tracks and for a group at 100", () => {
    expect(groupGain({ A: 25 }, track({ groupId: null }))).toBe(1);
    expect(groupGain({ A: 100 }, track({ groupId: "A" }))).toBe(1);
    expect(groupGain({}, track({ groupId: "B" }))).toBe(1);
  });

  it("scales grouped tracks", () => {
    expect(groupGain({ A: 50 }, track({ groupId: "A" }))).toBe(0.5);
    expect(groupGain({ A: 0 }, track({ groupId: "A" }))).toBe(0);
  });
});

describe("groupsInUse", () => {
  it("lists only groups with members, in A–D order", () => {
    const tracks = [
      track({ id: "t1", groupId: "C" }),
      track({ id: "t2", groupId: "A" }),
      track({ id: "t3", groupId: "A" }),
      track({ id: "t4", groupId: null }),
    ];
    expect(groupsInUse(tracks)).toEqual([
      { id: "A", count: 2 },
      { id: "C", count: 1 },
    ]);
  });
});
