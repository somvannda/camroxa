import { describe, expect, it, vi } from "vitest";
import { render, waitFor } from "@testing-library/react";

const peaks = (() => {
  const buckets = new Array(1024).fill(0.02);
  for (let beat = 0; beat <= 16; beat += 1) {
    const fraction = (beat * 0.5) / 8;
    buckets[Math.min(1023, Math.round(fraction * 1023))] = 1;
  }
  return buckets;
})();

vi.mock("@/lib/studio-peaks", async () => {
  const actual = await vi.importActual<typeof import("@/lib/studio-peaks")>("@/lib/studio-peaks");
  return { ...actual, computePeaks: vi.fn(async () => peaks) };
});

import { SongTempo } from "@/components/studio/StudioSongTempo";

describe("SongTempo", () => {
  it("measures the tempo from the audio instead of guessing", async () => {
    const { container } = render(<SongTempo url="/seed/steady.wav" duration={8} />);
    await waitFor(() => expect(container.textContent).toContain("120 BPM"));
  });

  it("renders nothing while the url or duration is missing", () => {
    const { container } = render(<SongTempo url={null} duration={8} />);
    expect(container.textContent).toBe("");
  });
});
