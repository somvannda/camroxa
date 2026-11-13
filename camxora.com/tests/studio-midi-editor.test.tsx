import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useState } from "react";

import { StudioMidiEditor } from "@/components/studio/StudioMidiEditor";
import type { MidiNote } from "@/lib/studio-midi";

afterEach(cleanup);

function renderEditor(overrides: Partial<React.ComponentProps<typeof StudioMidiEditor>> = {}) {
  const onChangeNotes = vi.fn();
  const onInstrumentChange = vi.fn();
  const view = render(
    <StudioMidiEditor
      clip={{ id: "clip", duration: 4, midi: { notes: [] } }}
      barWidth={96}
      secondsPerBar={2}
      loop={false}
      keyName="C"
      scaleName="off"
      instrument="triangle"
      onInstrumentChange={onInstrumentChange}
      onImportMidi={() => {}}
      onKeyChange={() => {}}
      onScaleChange={() => {}}
      onToggleLoop={() => {}}
      onChangeNotes={onChangeNotes}
      onChangeLanes={() => {}}
      onClose={() => {}}
      {...overrides}
    />
  );
  return { ...view, onChangeNotes, onInstrumentChange };
}

describe("StudioMidiEditor", () => {
  it("places a chord and an arpeggio from the toolbar modes", async () => {
    const user = userEvent.setup();
    const { container, onChangeNotes } = renderEditor();
    const grid = container.querySelector(".se-midi-grid") as HTMLElement;
    grid.getBoundingClientRect = () =>
      ({ left: 0, top: 0, width: 800, height: 600, right: 800, bottom: 600, x: 0, y: 0, toJSON: () => ({}) }) as DOMRect;

    await user.selectOptions(screen.getByLabelText("Chord mode"), "major");
    fireEvent.pointerDown(grid, { clientX: 100, clientY: 300, button: 0 });

    const chord = onChangeNotes.mock.calls.at(-1)?.[0] as Array<{ pitch: number; start: number }>;
    expect(chord.map((note) => note.pitch)).toEqual([59, 63, 66]);
    expect(chord.map((note) => note.start)).toEqual([2, 2, 2]);

    await user.selectOptions(screen.getByLabelText("Arpeggiator"), "up");
    fireEvent.pointerDown(grid, { clientX: 100, clientY: 300, button: 0 });

    const arp = onChangeNotes.mock.calls.at(-1)?.[0] as Array<{ pitch: number; start: number }>;
    expect(arp.map((note) => note.pitch)).toEqual([59, 63, 66]);
    expect(arp.map((note) => note.start)).toEqual([2, 2.25, 2.5]);
  });

  it("changes the synth instrument", async () => {
    const user = userEvent.setup();
    const { onInstrumentChange } = renderEditor();
    await user.selectOptions(screen.getByLabelText("MIDI instrument"), "sine");
    expect(onInstrumentChange).toHaveBeenCalledWith("sine");
  });

  it("commits a velocity drag without updating the parent mid-render", () => {
    const errors: unknown[][] = [];
    const spy = vi.spyOn(console, "error").mockImplementation((...args: unknown[]) => {
      errors.push(args);
    });
    const start: MidiNote[] = [
      { id: "n1", pitch: 60, start: 0, length: 0.5, velocity: 100 },
    ];
    // A real parent owns the notes, so a render-phase parent update would show up.
    function Harness() {
      const [notes, setNotes] = useState<MidiNote[]>(start);
      return (
        <StudioMidiEditor
          clip={{ id: "clip", duration: 4, midi: { notes } }}
          barWidth={96}
          secondsPerBar={2}
          loop={false}
          keyName="C"
          scaleName="off"
          instrument="triangle"
          onInstrumentChange={() => {}}
          onImportMidi={() => {}}
          onKeyChange={() => {}}
          onScaleChange={() => {}}
          onToggleLoop={() => {}}
          onChangeNotes={setNotes}
          onChangeLanes={() => {}}
          onClose={() => {}}
        />
      );
    }
    const { container } = render(<Harness />);
    const lane = container.querySelector(".se-midi-velocity") as HTMLElement;
    lane.getBoundingClientRect = () =>
      ({ left: 0, top: 0, width: 236, height: 64, right: 236, bottom: 64, x: 0, y: 0, toJSON: () => ({}) }) as DOMRect;

    fireEvent.pointerDown(lane, { clientX: 60, clientY: 20, button: 0 });
    fireEvent.pointerMove(window, { clientY: 50 });
    fireEvent.pointerUp(window);

    expect(errors).toEqual([]);
    const note = container.querySelector(".se-midi-note") as HTMLElement;
    expect(Number(note.getAttribute("data-velocity"))).toBeLessThan(100);
    spy.mockRestore();
  });
});
