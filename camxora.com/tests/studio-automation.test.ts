import { describe, expect, it, vi } from "vitest";

import {
  automationValueAt,
  sanitizeAutomation,
  schedulePanAutomation,
  scheduleVolumeAutomation,
} from "@/lib/studio-automation";

describe("track automation", () => {
  it("sanitises, clamps and sorts points", () => {
    expect(
      sanitizeAutomation(
        [
          { id: "b", time: 4, value: 120 },
          { time: 1, value: 25 },
          { time: "x", value: 3 },
          null,
        ],
        0,
        100
      )
    ).toEqual([
      { id: "auto-1", time: 1, value: 25 },
      { id: "b", time: 4, value: 100 },
    ]);
  });

  it("interpolates between points and holds the ends", () => {
    const points = [
      { id: "a", time: 0, value: 0 },
      { id: "b", time: 10, value: 100 },
    ];
    expect(automationValueAt([], 5, 80)).toBe(80);
    expect(automationValueAt(points, -1, 80)).toBe(0);
    expect(automationValueAt(points, 5, 80)).toBe(50);
    expect(automationValueAt(points, 20, 80)).toBe(100);
  });

  it("schedules the initial value and later ramps", () => {
    const param = {
      cancelScheduledValues: vi.fn(),
      setValueAtTime: vi.fn(),
      linearRampToValueAtTime: vi.fn(),
    } as unknown as AudioParam;

    scheduleVolumeAutomation(
      param,
      [
        { id: "a", time: 2, value: 20 },
        { id: "b", time: 6, value: 80 },
      ],
      { from: 2, when: 10, rate: 1, fallback: 50 }
    );

    expect(param.cancelScheduledValues).toHaveBeenCalledWith(10);
    expect(param.setValueAtTime).toHaveBeenCalledWith(0.2, 10);
    expect(param.linearRampToValueAtTime).toHaveBeenCalledWith(0.8, 14);
  });

  it("schedules pan ramps on the -1..1 scale", () => {
    const param = {
      cancelScheduledValues: vi.fn(),
      setValueAtTime: vi.fn(),
      linearRampToValueAtTime: vi.fn(),
    } as unknown as AudioParam;

    schedulePanAutomation(
      param,
      [
        { id: "a", time: 1, value: -50 },
        { id: "b", time: 5, value: 50 },
      ],
      { from: 1, when: 0, rate: 1, fallback: 0 }
    );

    expect(param.setValueAtTime).toHaveBeenCalledWith(-0.5, 0);
    expect(param.linearRampToValueAtTime).toHaveBeenCalledWith(0.5, 4);
  });
});
