import { describe, expect, it } from "vitest";

import {
  effectiveTrackMix,
  sanitizeGroups,
  type StudioGroup,
} from "@/lib/studio-groups";

const groups: StudioGroup[] = [
  { id: "g1", name: "Drums", color: "#ff0000", volume: 50, muted: false, solo: false },
  { id: "g2", name: "Bass", color: "#00ff00", volume: 100, muted: false, solo: false },
];

describe("track groups", () => {
  it("sanitises group rows", () => {
    expect(
      sanitizeGroups([
        { id: "a", name: "Drums", volume: 120, muted: 1 },
        { id: "a", name: "Duplicate" },
        { id: 3, name: "Bad" },
        null,
      ])
    ).toEqual([
      { id: "a", name: "Drums", color: "#38bdf8", volume: 100, muted: true, solo: false },
    ]);
  });

  it("scales volume and applies group mute", () => {
    expect(
      effectiveTrackMix({ volume: 80, muted: false, solo: false, groupId: "g1" }, groups, false)
    ).toEqual({ volume: 40, muted: false, solo: false });

    const muted = [{ ...groups[0], muted: true }];
    expect(
      effectiveTrackMix({ volume: 80, muted: false, solo: false, groupId: "g1" }, muted, false)
        .muted
    ).toBe(true);
  });

  it("a soloed group isolates its members", () => {
    const soloed = [{ ...groups[0], solo: true }, groups[1]];
    expect(
      effectiveTrackMix({ volume: 80, muted: false, solo: false, groupId: "g1" }, soloed, false)
    ).toMatchObject({ muted: false, solo: true });
    expect(
      effectiveTrackMix({ volume: 80, muted: false, solo: false, groupId: "g2" }, soloed, false)
    ).toMatchObject({ muted: true, solo: false });
    expect(
      effectiveTrackMix({ volume: 80, muted: false, solo: false, groupId: null }, soloed, false)
    ).toMatchObject({ muted: true, solo: false });
  });
});
