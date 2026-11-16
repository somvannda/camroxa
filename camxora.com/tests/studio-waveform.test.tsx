import { describe, expect, it, vi } from "vitest";
import { render, waitFor } from "@testing-library/react";

const state = vi.hoisted(() => ({ peaks: null as number[] | null }));

vi.mock("@/lib/studio-peaks", async () => {
  const actual = await vi.importActual<typeof import("@/lib/studio-peaks")>("@/lib/studio-peaks");
  return { ...actual, computePeaks: vi.fn(async () => state.peaks) };
});

import { Waveform } from "@/components/studio/Waveform";

/**
 * QA C1: a failed fetch/decode used to leave an invisible canvas, so timeline clips
 * looked like flat colour blocks with no waveform. The canvas must always say which
 * state it is in.
 */
describe("Waveform", () => {
  it("paints peaks and marks itself ready", async () => {
    state.peaks = new Array(1024).fill(0.4);
    const { container } = render(<Waveform url="/seed/demo-loop.wav" width={120} height={30} label="Song waveform" />);
    await waitFor(() =>
      expect(container.querySelector("canvas")?.getAttribute("data-waveform")).toBe("ready")
    );
  });

  it("falls back to a baseline when the audio cannot be decoded", async () => {
    state.peaks = null;
    const { container } = render(<Waveform url="/seed/broken.wav" width={120} height={30} label="Song waveform" />);
    await waitFor(() =>
      expect(container.querySelector("canvas")?.getAttribute("data-waveform")).toBe("fallback")
    );
    expect(container.querySelector("canvas")?.getAttribute("aria-label")).toBe("Song waveform");
  });

  it("is a fallback, not a pending ghost, without a url", async () => {
    state.peaks = null;
    const { container } = render(<Waveform url={null} width={120} height={30} label="Song waveform" />);
    await waitFor(() =>
      expect(container.querySelector("canvas")?.getAttribute("data-waveform")).toBe("fallback")
    );
  });
});
