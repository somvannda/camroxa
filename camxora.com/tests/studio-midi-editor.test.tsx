import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { StudioMidiEditor } from "@/components/studio/StudioMidiEditor";

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
});
