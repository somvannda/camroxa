import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { StudioAudioEditor, type AudioEditorClip } from "@/components/studio/StudioAudioEditor";
import type { WarpState } from "@/lib/studio-warp";

afterEach(cleanup);

function clip(overrides: Partial<AudioEditorClip> = {}): AudioEditorClip {
  return {
    id: "clip-1",
    title: "Loop",
    color: "#38bdf8",
    start: 0,
    duration: 4,
    audioUrl: null,
    ...overrides,
  };
}

const baseProps = {
  secondsPerBar: 2,
  beatsPerBar: 4,
  playhead: 1,
  onClose: () => {},
};

describe("StudioAudioEditor", () => {
  it("starts with stretch off and no markers", () => {
    render(<StudioAudioEditor {...baseProps} clip={clip()} onWarp={() => {}} />);

    expect(
      screen.getByRole("switch", { name: "Stretch" }).getAttribute("aria-checked")
    ).toBe("false");
    expect(document.querySelectorAll(".se-warp-head")).toHaveLength(0);
    expect(screen.getByText(/Stretch is off/)).toBeTruthy();
  });

  it("fills the clip with On Beat markers and switches stretch on", async () => {
    const user = userEvent.setup();
    const onWarp = vi.fn();
    render(<StudioAudioEditor {...baseProps} clip={clip()} onWarp={onWarp} />);

    await user.click(screen.getByRole("radio", { name: "On Beat" }));

    expect(onWarp).toHaveBeenCalledTimes(1);
    const next = onWarp.mock.calls[0][0] as WarpState;
    expect(next.on).toBe(true);
    expect(next.mode).toBe("beat");
    // 4 s of 2 s bars in 4/4: a marker every beat, both bounds included.
    expect(next.markers).toHaveLength(9);
    expect(next.markers.map((marker) => marker.time)).toEqual([0, 0.5, 1, 1.5, 2, 2.5, 3, 3.5, 4]);
  });

  it("places the captured modes' markers and the Formant control", async () => {
    const user = userEvent.setup();
    const onWarp = vi.fn();
    render(<StudioAudioEditor {...baseProps} clip={clip()} onWarp={onWarp} />);

    await user.click(screen.getByRole("radio", { name: "Start and End" }));
    const startEnd = onWarp.mock.calls[0][0] as WarpState;
    expect(startEnd.markers.map((marker) => marker.time)).toEqual([0, 4]);

    await user.type(screen.getByLabelText("Formant"), "40");
    expect(onWarp).toHaveBeenCalled();
  });

  it("draws a pennant head per marker and selects on click", async () => {
    const user = userEvent.setup();
    const warp: WarpState = {
      on: true,
      mode: "beat",
      formant: 0,
      markers: [
        { id: "a", time: 0, source: 0 },
        { id: "b", time: 1, source: 1 },
        { id: "c", time: 2, source: 2 },
      ],
    };
    render(
      <StudioAudioEditor {...baseProps} clip={clip({ warp })} onWarp={() => {}} />
    );

    const heads = document.querySelectorAll(".se-warp-head");
    expect(heads).toHaveLength(3);

    await user.click(heads[1] as HTMLElement);
    expect(heads[1].getAttribute("aria-pressed")).toBe("true");
    expect(screen.getByText(/3 markers/)).toBeTruthy();
  });

  it("switches stretch off without dropping the markers", async () => {
    const user = userEvent.setup();
    const onWarp = vi.fn();
    const warp: WarpState = {
      on: true,
      mode: "transients",
      formant: 20,
      markers: [{ id: "a", time: 0, source: 0 }],
    };
    render(<StudioAudioEditor {...baseProps} clip={clip({ warp })} onWarp={onWarp} />);

    await user.click(screen.getByRole("switch", { name: "Stretch" }));

    expect(onWarp).toHaveBeenCalledWith(
      expect.objectContaining({ on: false, formant: 20, markers: warp.markers })
    );
  });
});
