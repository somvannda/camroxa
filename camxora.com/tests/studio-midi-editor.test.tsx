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

  describe("captured keyboard shortcuts (S14)", () => {
    const notes = [
      { id: "n1", pitch: 60, start: 0.1, length: 0.4, velocity: 100 },
      { id: "n2", pitch: 64, start: 0.35, length: 0.4, velocity: 100 },
    ];

    function renderWithNotes() {
      const view = renderEditor({ clip: { id: "clip", duration: 4, midi: { notes } } });
      const section = view.container.querySelector(".se-midi") as HTMLElement;
      return { ...view, section };
    }

    const selectAll = (section: HTMLElement) =>
      fireEvent.keyDown(section, { key: "a", ctrlKey: true });

    it("selects every note with Ctrl A and transposes the selection", () => {
      const { section, onChangeNotes, container } = renderWithNotes();
      selectAll(section);
      expect(container.querySelectorAll(".se-midi-note.is-selected")).toHaveLength(2);

      fireEvent.keyDown(section, { key: "ArrowUp" });
      const raised = onChangeNotes.mock.calls.at(-1)?.[0] as MidiNote[];
      expect(raised.map((note) => note.pitch)).toEqual([61, 65]);

      fireEvent.keyDown(section, { key: "ArrowDown", shiftKey: true });
      // The mock does not feed the previous patch back as a prop, so this is
      // measured from the original pitches: shift transposes by an octave.
      const dropped = onChangeNotes.mock.calls.at(-1)?.[0] as MidiNote[];
      expect(dropped.map((note) => note.pitch)).toEqual([48, 52]);
    });

    it("nudges selected notes by the quantize grid", () => {
      const { section, onChangeNotes } = renderWithNotes();
      selectAll(section);
      // Default grid is 1/8, so with two seconds per bar a step is 0.25s.
      fireEvent.keyDown(section, { key: "ArrowRight" });
      const moved = onChangeNotes.mock.calls.at(-1)?.[0] as MidiNote[];
      expect(moved[0].start).toBeCloseTo(0.35, 6);
      expect(moved[1].start).toBeCloseTo(0.6, 6);

      // Shift ↔ lengthens the selection instead of moving it.
      fireEvent.keyDown(section, { key: "ArrowRight", shiftKey: true });
      const longer = onChangeNotes.mock.calls.at(-1)?.[0] as MidiNote[];
      expect(longer[0].length).toBeCloseTo(0.65, 6);
      expect(longer[0].start).toBeCloseTo(0.1, 6);
    });

    it("toggles notes disabled with 0 and marks them in the grid", () => {
      const { section, onChangeNotes, rerender } = renderWithNotes();
      selectAll(section);
      fireEvent.keyDown(section, { key: "0" });
      const muted = onChangeNotes.mock.calls.at(-1)?.[0] as MidiNote[];
      expect(muted.every((note) => note.disabled === true)).toBe(true);

      rerender(
        <StudioMidiEditor
          clip={{ id: "clip", duration: 4, midi: { notes: muted } }}
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
          onChangeNotes={onChangeNotes}
          onChangeLanes={() => {}}
          onClose={() => {}}
        />
      );
      expect(document.querySelectorAll(".se-midi-note.is-disabled")).toHaveLength(2);
    });

    it("quantizes the selection with Shift Q", () => {
      const { section, onChangeNotes } = renderWithNotes();
      selectAll(section);
      fireEvent.keyDown(section, { key: "Q", shiftKey: true });
      const quantized = onChangeNotes.mock.calls.at(-1)?.[0] as MidiNote[];
      expect(quantized.map((note) => note.start)).toEqual([0, 0.25]);
    });

    it("deletes the selection and closes the grid on Escape", () => {
      const { section, onChangeNotes, container } = renderWithNotes();
      selectAll(section);
      fireEvent.keyDown(section, { key: "Delete" });
      expect(onChangeNotes.mock.calls.at(-1)?.[0]).toEqual([]);

      selectAll(section);
      fireEvent.keyDown(section, { key: "Escape" });
      expect(container.querySelectorAll(".se-midi-note.is-selected")).toHaveLength(0);
    });

    it("doubles or halves the grid with Shift 1 and Shift 2", () => {
      const { section } = renderWithNotes();
      const quantize = screen.getByLabelText("Quantize") as HTMLSelectElement;
      fireEvent.keyDown(section, { key: "!", shiftKey: true });
      expect(quantize.value).toBe("16");
      fireEvent.keyDown(section, { key: "@", shiftKey: true });
      expect(quantize.value).toBe("8");
    });
  });
});
