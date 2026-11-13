import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
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

  it("writes the captured clip settings", async () => {
    const user = userEvent.setup();
    const onAudio = vi.fn();
    const { rerender } = render(
      <StudioAudioEditor {...baseProps} clip={clip()} onWarp={() => {}} onAudio={onAudio} />
    );

    fireEvent.change(screen.getByLabelText("Volume"), { target: { value: "-6" } });
    expect(onAudio).toHaveBeenLastCalledWith(expect.objectContaining({ gainDb: -6 }));

    await user.click(screen.getByRole("button", { name: /Loop/ }));
    expect(onAudio).toHaveBeenLastCalledWith(expect.objectContaining({ loop: true }));

    rerender(
      <StudioAudioEditor
        {...baseProps}
        clip={clip({ audio: { loop: true, reverse: false, gainDb: -6 } })}
        onWarp={() => {}}
        onAudio={onAudio}
      />
    );
    await user.click(screen.getByRole("button", { name: /Reverse/ }));
    expect(onAudio).toHaveBeenLastCalledWith(
      expect.objectContaining({ reverse: true, loop: true })
    );
  });

  it("steps pitch within the captured range", async () => {
    const user = userEvent.setup();
    const onAudio = vi.fn();
    render(
      <StudioAudioEditor {...baseProps} clip={clip()} onWarp={() => {}} onAudio={onAudio} />
    );

    await user.click(screen.getByRole("button", { name: "Raise pitch" }));
    expect(onAudio).toHaveBeenLastCalledWith(expect.objectContaining({ pitch: 1 }));

    cleanup();
    render(
      <StudioAudioEditor
        {...baseProps}
        clip={clip({ audio: { pitch: 12 } })}
        onWarp={() => {}}
        onAudio={onAudio}
      />
    );
    expect(
      (screen.getByRole("button", { name: "Raise pitch" }) as HTMLButtonElement).disabled
    ).toBe(true);
  });

  it("toggles the speed presets and their readout", async () => {
    const user = userEvent.setup();
    const onAudio = vi.fn();
    const { rerender } = render(
      <StudioAudioEditor {...baseProps} clip={clip()} onWarp={() => {}} onAudio={onAudio} />
    );

    await user.click(screen.getByRole("button", { name: "×½" }));
    expect(onAudio).toHaveBeenLastCalledWith(expect.objectContaining({ speed: 50 }));

    rerender(
      <StudioAudioEditor
        {...baseProps}
        clip={clip({ audio: { speed: 50 } })}
        onWarp={() => {}}
        onAudio={onAudio}
      />
    );
    expect(screen.getByText("50%")).toBeTruthy();
    await user.click(screen.getByRole("button", { name: "×½" }));
    expect(onAudio).toHaveBeenLastCalledWith(expect.objectContaining({ speed: 100 }));
  });

  it("quantizes markers onto the picked grid", async () => {
    const user = userEvent.setup();
    const onWarp = vi.fn();
    const warp: WarpState = {
      on: true,
      mode: "transients",
      formant: 0,
      markers: [
        { id: "a", time: 0.1, source: 0.1 },
        { id: "b", time: 0.6, source: 0.6 },
        { id: "c", time: 1.4, source: 1.4 },
      ],
    };
    render(<StudioAudioEditor {...baseProps} clip={clip({ warp })} onWarp={onWarp} />);

    await user.click(screen.getByRole("button", { name: "1/4" }));
    await user.click(screen.getByRole("button", { name: "Quantize" }));

    const next = onWarp.mock.calls.at(-1)?.[0] as WarpState;
    // 2 s bars in 4/4: a 1/4 grid is 0.5 s.
    expect(next.markers.map((marker) => marker.time)).toEqual([0, 0.5, 1.5]);
  });

  it("steps the quantize grid finer and coarser with Shift 1 / Shift 2", () => {
    const warp: WarpState = {
      on: true,
      mode: "beat",
      formant: 0,
      markers: [{ id: "a", time: 0, source: 0 }],
    };
    render(<StudioAudioEditor {...baseProps} clip={clip({ warp })} onWarp={() => {}} />);
    const pressed = () =>
      document.querySelector(".se-audio-grid button[aria-pressed='true']")?.textContent;

    expect(pressed()).toBe("1/8");
    fireEvent.keyDown(window, { key: "!", shiftKey: true });
    expect(pressed()).toBe("1/16");
    fireEvent.keyDown(window, { key: "!", shiftKey: true });
    expect(pressed()).toBe("1/32");
    // The grid stops at the coarsest / finest captured chip.
    fireEvent.keyDown(window, { key: "!", shiftKey: true });
    expect(pressed()).toBe("1/32");
    fireEvent.keyDown(window, { key: "@", shiftKey: true });
    expect(pressed()).toBe("1/16");
  });
});
