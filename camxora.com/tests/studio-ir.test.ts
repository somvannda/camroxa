import { describe, expect, it } from "vitest";

import {
  IMPULSE_CATEGORIES,
  IMPULSE_RESPONSES,
  customImpulseResponses,
  designImpulseResponse,
  findImpulseResponse,
  impulseEnvelope,
  impulseLabel,
  saveCustomImpulseResponse,
} from "@/lib/studio-ir";

describe("impulse response library (S44)", () => {
  it("ships eleven responses across six groups", () => {
    expect(IMPULSE_RESPONSES).toHaveLength(11);
    expect(IMPULSE_CATEGORIES).toHaveLength(6);
    expect(IMPULSE_CATEGORIES.map((group) => group.label)).toContain("Halls");
  });

  it("labels a selection as category › name", () => {
    expect(impulseLabel("new-england-hall")).toBe("Halls › New England Hall");
    expect(impulseLabel(null)).toBe("");
    expect(impulseLabel("missing")).toBe("");
  });

  it("finds responses by id", () => {
    expect(findImpulseResponse("small-room")?.seconds).toBeCloseTo(0.8);
    expect(findImpulseResponse("nope")).toBeNull();
  });

  it("designs, clamps and saves a custom response", () => {
    const response = designImpulseResponse({ name: "Studio Plate", seconds: 99, decay: 0.1 });
    expect(response.category).toBe("Custom");
    expect(response.seconds).toBe(8);
    expect(response.decay).toBe(0.2);

    saveCustomImpulseResponse(response);
    expect(findImpulseResponse(response.id)).toEqual(response);
    expect(customImpulseResponses().some((item) => item.id === response.id)).toBe(true);
  });

  it("draws a deterministic decaying envelope", () => {
    const hall = findImpulseResponse("new-england-hall");
    if (!hall) throw new Error("missing hall");
    const envelope = impulseEnvelope(hall, 64);
    expect(envelope).toHaveLength(64);
    expect(envelope[0]).toBeGreaterThan(0.5);
    expect(envelope[63]).toBeLessThan(0.2);
    expect(impulseEnvelope(hall, 64)).toEqual(envelope);
  });
});
