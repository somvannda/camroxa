import { describe, expect, it } from "vitest";

import { makeUserPreset, userPresetsFor, type UserPreset } from "@/lib/studio-plugins";

const presets: UserPreset[] = [
  { id: "preset-a", name: "My Glue", pluginId: "compressor", params: { threshold: -18 } },
  { id: "preset-b", name: "Air", pluginId: "eq", params: { band1: 4 } },
];

describe("userPresetsFor", () => {
  it("keeps only the presets of the requested plugin", () => {
    expect(userPresetsFor(presets, "compressor")).toEqual([presets[0]]);
    expect(userPresetsFor(presets, "eq")).toEqual([presets[1]]);
    expect(userPresetsFor(presets, "reverb")).toEqual([]);
    expect(userPresetsFor(undefined, "eq")).toEqual([]);
  });
});

describe("makeUserPreset", () => {
  it("names and copies the settings, with a stable id", () => {
    const params = { threshold: -12 };
    const preset = makeUserPreset("compressor", "  My Glue  ", params, "vocal", "s1");

    expect(preset).toEqual({
      id: "preset-s1",
      name: "My Glue",
      pluginId: "compressor",
      params: { threshold: -12 },
      mode: "vocal",
    });
    // The params are copied, so later knob moves cannot mutate a saved preset.
    params.threshold = -30;
    expect(preset.params.threshold).toBe(-12);
  });

  it("falls back to a name and omits an empty mode", () => {
    const preset = makeUserPreset("eq", "   ", { band1: 2 }, undefined, "s2");
    expect(preset.name).toBe("My preset");
    expect(preset).not.toHaveProperty("mode");
  });
});
