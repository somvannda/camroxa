import { describe, expect, it } from "vitest";

import { sanitizeChain } from "@/lib/studio-plugin-chain";
import { sanitizeParams } from "@/lib/studio-plugins";

describe("Rhythm Gate catalog", () => {
  it("migrates a persisted chorus entry instead of dropping it", () => {
    const chain = sanitizeChain([
      {
        entryId: "fx-old",
        pluginId: "chorus",
        params: { rate: 0.8, depth: 40, mix: 30 },
      },
    ]);
    expect(chain).toHaveLength(1);
    expect(chain[0].pluginId).toBe("rhythmGate");
    // 0.8 Hz was the old default; the slowest valid division is 1/4.
    expect(chain[0].params.rate).toBe(2);
    expect(chain[0].params.depth).toBeCloseTo(0.4);
    expect(chain[0].params.mix).toBeCloseTo(0.3);
  });

  it("clamps rate to a real division and percentages to 0–1", () => {
    const params = sanitizeParams("rhythmGate", { rate: 99, depth: 2, mix: -1 });
    expect(params.rate).toBe(2);
    expect(params.depth).toBe(1);
    expect(params.mix).toBe(0);
  });
});
