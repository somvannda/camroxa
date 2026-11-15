import { describe, expect, it } from "vitest";

import { sanitizeSends, sendsActive } from "@/lib/studio-sends";
import { sanitizeTracks } from "@/lib/studio-tracks";

describe("sanitizeSends", () => {
  it("clamps levels to 0–100 and defaults missing fields to 0", () => {
    expect(sanitizeSends({ delay: 140, reverb: -5 })).toEqual({ delay: 100, reverb: 0 });
    expect(sanitizeSends({ delay: 30 })).toEqual({ delay: 30, reverb: 0 });
  });

  it("treats junk as dry", () => {
    expect(sanitizeSends(null)).toEqual({ delay: 0, reverb: 0 });
    expect(sanitizeSends("nope")).toEqual({ delay: 0, reverb: 0 });
  });
});

describe("sendsActive", () => {
  it("is true only when a bus is fed", () => {
    expect(sendsActive({ delay: 0, reverb: 0 })).toBe(false);
    expect(sendsActive({ delay: 0, reverb: 1 })).toBe(true);
  });
});

describe("track sanitisation", () => {
  it("keeps sends and a known group, and drops an unknown group", () => {
    const [track] = sanitizeTracks([
      { id: "t1", clipIds: [], sends: { delay: 20, reverb: 60 }, groupId: "B" },
    ]);
    expect(track.sends).toEqual({ delay: 20, reverb: 60 });
    expect(track.groupId).toBe("B");

    const [unknown] = sanitizeTracks([{ id: "t2", clipIds: [], groupId: "Z" }]);
    expect(unknown.groupId).toBeNull();
    expect(unknown.sends).toEqual({ delay: 0, reverb: 0 });
  });
});
