import { describe, expect, it } from "vitest";

import { NOTE_DIVISIONS, divisionMs, nearestDivisionLabel } from "@/lib/studio-plugins";

/**
 * The Delay declared `tempoSynced` on its Time knob but nothing read it, so Tempo mode
 * still showed milliseconds (found by the W5 prep enumeration). These pin the conversion.
 */
describe("tempo-synced delay", () => {
  it("converts a division to milliseconds at the project tempo", () => {
    expect(divisionMs(1, 120)).toBe(500);
    expect(divisionMs(0.5, 120)).toBe(250);
    expect(divisionMs(0.25, 120)).toBe(125);
    expect(divisionMs(4, 60)).toBe(4000);
  });

  it("clamps an unusable tempo instead of dividing by zero", () => {
    expect(divisionMs(1, 0)).toBe(500);
    expect(divisionMs(1, Number.NaN)).toBe(500);
    expect(divisionMs(1, 120)).toBe(500);
  });

  it("picks the nearest division for a free-running value", () => {
    expect(nearestDivisionLabel(250, 120)).toBe("1/8");
    expect(nearestDivisionLabel(490, 120)).toBe("1/4");
    expect(nearestDivisionLabel(1900, 120)).toBe("1 bar");
  });

  it("offers the six captured divisions", () => {
    expect(NOTE_DIVISIONS.map((division) => division.label)).toEqual([
      "1/32",
      "1/16",
      "1/8",
      "1/4",
      "1/2",
      "1 bar",
    ]);
  });
});
