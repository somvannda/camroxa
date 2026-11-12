import { describe, expect, it } from "vitest";

import { beatAt, clicksBetween } from "@/lib/studio-metronome";

describe("clicksBetween", () => {
  it("puts a beat at the start when the window opens on one", () => {
    const clicks = clicksBetween(0, 1, 120);
    expect(clicks.map((click) => Number(click.time.toFixed(3)))).toEqual([0, 0.5]);
  });

  it("is half-open: the beat exactly at the window end belongs to the next call", () => {
    expect(clicksBetween(0.5, 1, 120).map((click) => Number(click.time.toFixed(3)))).toEqual([0.5]);
    expect(clicksBetween(1, 1.5, 120).map((click) => Number(click.time.toFixed(3)))).toEqual([1]);
  });

  it("accents the first beat of each bar", () => {
    const clicks = clicksBetween(0, 2.1, 120);
    expect(clicks.filter((click) => click.accent).map((click) => Number(click.time.toFixed(3)))).toEqual([
      0, 2,
    ]);
  });

  it("follows the tempo", () => {
    // 60 BPM = one beat per second.
    expect(clicksBetween(0, 2.5, 60).length).toBe(3);
    // 240 BPM = four per second.
    expect(clicksBetween(0, 2.5, 240).length).toBe(10);
  });

  it("returns nothing for an empty or invalid window", () => {
    expect(clicksBetween(1, 1, 120)).toEqual([]);
    expect(clicksBetween(2, 1, 120)).toEqual([]);
    expect(clicksBetween(0, 1, 0)).toEqual([]);
    expect(clicksBetween(0, 1, -120)).toEqual([]);
  });

  it("works from an arbitrary offset (loop wrap or seek)", () => {
    const clicks = clicksBetween(10, 10.6, 120);
    expect(clicks.map((click) => Number(click.time.toFixed(3)))).toEqual([10, 10.5]);
    // Beat 20 is the start of bar 6, so it is accented.
    expect(clicks[0].accent).toBe(true);
  });
});

describe("beatAt", () => {
  it("reports a 1-based beat within the bar", () => {
    expect(beatAt(0, 120)).toBe(1);
    expect(beatAt(0.5, 120)).toBe(2);
    expect(beatAt(1.5, 120)).toBe(4);
    expect(beatAt(2, 120)).toBe(1);
  });

  it("never reports a beat before time zero or without a tempo", () => {
    expect(beatAt(-1, 120)).toBe(0);
    expect(beatAt(1, 0)).toBe(0);
  });
});
