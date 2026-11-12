import { describe, expect, it } from "vitest";

import {
  applyMasterPreset,
  LIMITER_DEFAULTS,
  MASTER_PRESETS,
  type MasterChainEntry,
} from "@/lib/studio-master-bus";

const limiter: MasterChainEntry = {
  id: "limiter",
  type: "limiter",
  enabled: true,
  params: { ...LIMITER_DEFAULTS, preGain: 2 },
};

const preset = (id: string) => {
  const found = MASTER_PRESETS.find((item) => item.id === id);
  if (!found) throw new Error(`missing preset ${id}`);
  return found;
};

describe("master presets", () => {
  it("Default keeps the captured Limiter-only chain", () => {
    const next = applyMasterPreset(
      [
        limiter,
        { id: "eq", type: "eq", enabled: true, amount: 0.6 },
        { id: "comp", type: "compressor", enabled: true, amount: 0.4 },
      ],
      preset("default")
    );
    expect(next).toHaveLength(1);
    expect(next[0].type).toBe("limiter");
    expect(next[0].params).toMatchObject(LIMITER_DEFAULTS);
  });

  it("Warm sets the limiter and adds EQ + compressor links", () => {
    const next = applyMasterPreset([limiter], preset("warm"));
    const limiterEntry = next.find((entry) => entry.type === "limiter");
    expect(limiterEntry?.params).toMatchObject({ preGain: 1.5, attack: 15, release: 140 });
    expect(next.find((entry) => entry.type === "eq")?.amount).toBe(0.6);
    expect(next.find((entry) => entry.type === "compressor")?.amount).toBe(0.25);
  });

  it("Loud updates existing links instead of duplicating them", () => {
    const next = applyMasterPreset(
      [
        limiter,
        { id: "eq", type: "eq", enabled: true, amount: 0.1 },
        { id: "comp", type: "compressor", enabled: true, amount: 0.1 },
      ],
      preset("loud")
    );
    expect(next.filter((entry) => entry.type === "eq")).toHaveLength(1);
    expect(next.filter((entry) => entry.type === "compressor")).toHaveLength(1);
    expect(next.find((entry) => entry.type === "eq")?.amount).toBe(0.55);
    expect(next.find((entry) => entry.type === "compressor")?.amount).toBe(0.6);
  });

  it("adds a limiter when the chain has none", () => {
    const next = applyMasterPreset([], preset("clean"));
    expect(next[0].type).toBe("limiter");
    expect(next[0].params).toMatchObject({ attack: 10, release: 120 });
  });
});
