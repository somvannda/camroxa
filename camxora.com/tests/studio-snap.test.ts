import { describe, expect, it } from "vitest";

import { DRAG_THRESHOLD_PX, dragToStart, isDrag, snapToGrid } from "@/lib/studio-snap";

describe("snapToGrid", () => {
  it("snaps to beats when a bar is 2s and the grid is 4", () => {
    expect(snapToGrid(0.1, 2, 4)).toBe(0);
    expect(snapToGrid(0.6, 2, 4)).toBe(0.5);
    expect(snapToGrid(1.3, 2, 4)).toBe(1.5);
  });

  it("clamps at zero", () => {
    expect(snapToGrid(-3, 2, 4)).toBe(0);
  });

  it("is a no-op for a degenerate bar length", () => {
    expect(snapToGrid(1.234, 0, 4)).toBe(1.234);
  });
});

describe("dragToStart", () => {
  it("moves exactly one bar for one bar of pixels", () => {
    expect(dragToStart(0, 96, 96, 2, 4)).toBe(2);
    expect(dragToStart(4, -96, 96, 2, 4)).toBe(2);
  });

  it("snaps a sub-bar drag to the nearest beat", () => {
    // 40px of a 96px bar at 2s/bar is 0.83s, which is nearer one beat (0.5) than zero:
    expect(dragToStart(0, 40, 96, 2, 4)).toBe(1);
    // 20px is 0.42s, which rounds down to half a beat.
    expect(dragToStart(0, 20, 96, 2, 4)).toBe(0.5);
  });

  it("never returns a negative start", () => {
    expect(dragToStart(0, -500, 96, 2, 4)).toBe(0);
  });

  it("honours a disabling division count", () => {
    expect(dragToStart(0, 48, 96, 2, 0)).toBe(1);
  });
});

describe("isDrag", () => {
  it("ignores pointer jitter below the threshold", () => {
    expect(isDrag(0)).toBe(false);
    expect(isDrag(DRAG_THRESHOLD_PX)).toBe(false);
  });

  it("treats movement past the threshold as a drag in either direction", () => {
    expect(isDrag(DRAG_THRESHOLD_PX + 1)).toBe(true);
    expect(isDrag(-(DRAG_THRESHOLD_PX + 1))).toBe(true);
  });
});
