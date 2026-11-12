import { describe, expect, it } from "vitest";

import { sanitizeSectionMarkers } from "@/lib/studio-markers";

describe("section markers", () => {
  it("keeps valid markers, sorts them and supplies defaults", () => {
    const markers = sanitizeSectionMarkers([
      { id: "b", time: 12.5, label: "Chorus", color: "#ff0000" },
      { time: 0, label: "Intro" },
      { time: "not a number", label: "Broken" },
      null,
    ]);
    expect(markers).toEqual([
      { id: "marker-0", time: 0, label: "Intro", color: "#3dafff" },
      { id: "b", time: 12.5, label: "Chorus", color: "#ff0000" },
    ]);
  });

  it("returns an empty list for bad input", () => {
    expect(sanitizeSectionMarkers(undefined)).toEqual([]);
    expect(sanitizeSectionMarkers("nope")).toEqual([]);
  });
});
