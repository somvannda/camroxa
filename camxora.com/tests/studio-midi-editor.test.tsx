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

  describe("overview strip (S31)", () => {
    const notes: MidiNote[] = [
      { id: "n1", pitch: 60, start: 0, length: 0.5, velocity: 100 },
      { id: "n2", pitch: 67, start: 4, length: 1, velocity: 100 },
    ];

    /** 8 s at 2 s/bar × 96 px = a 384 px clip; the roll gets a 200 px viewport (156 grid px). */
    function renderOverview() {
      const view = renderEditor({ clip: { id: "clip", duration: 8, midi: { notes } } });
      const roll = view.container.querySelector(".se-midi-roll") as HTMLElement;
      const track = view.container.querySelector(".se-midi-overview-track") as HTMLElement;
      const windowEl = view.container.querySelector(".se-midi-overview-window") as HTMLElement;
      Object.defineProperty(roll, "clientWidth", { configurable: true, value: 200 });
      track.getBoundingClientRect = () =>
        ({ left: 0, top: 0, width: 400, height: 18, right: 400, bottom: 18, x: 0, y: 0, toJSON: () => ({}) }) as DOMRect;
      fireEvent.scroll(roll);
      return { ...view, roll, track, windowEl };
    }

    it("maps the clip's notes and marks the visible slice as a window", () => {
      const { container, track, windowEl } = renderOverview();
      const minimapNotes = Array.from(container.querySelectorAll(".se-midi-overview-note"));
      expect(minimapNotes).toHaveLength(2);
      expect((minimapNotes[0] as HTMLElement).style.left).toBe("0%");
      expect((minimapNotes[1] as HTMLElement).style.left).toBe("50%");

      expect(track.getAttribute("role")).toBe("slider");
      expect(parseFloat(windowEl.style.left)).toBe(0);
      // 156 visible grid px of 384 → 40.6 % of the clip.
      expect(parseFloat(windowEl.style.width)).toBeCloseTo(40.625, 2);
      expect(track.getAttribute("aria-valuetext")).toMatch(/^Bars 1\.0–/);
      expect(track.getAttribute("aria-valuetext")).toContain("of 4.0");

      expect(parseFloat((container.querySelector(".se-midi-grid") as HTMLElement).style.width)).toBe(
        384
      );
    });

    it("scrolls the roll to the point that is clicked", () => {
      const { roll, track, windowEl, onChangeNotes } = renderOverview();
      fireEvent.pointerDown(track, { clientX: 300, button: 0 });

      // 75 % of the clip centred in a 156 px viewport: 288 − 78 = 210.
      expect(roll.scrollLeft).toBe(210);
      expect(parseFloat(windowEl.style.left)).toBeCloseTo((210 / 384) * 100, 2);
      expect(track.getAttribute("aria-valuenow")).toBe("92");
      expect(onChangeNotes).not.toHaveBeenCalled();
    });

    it("drags the window without jumping when it is grabbed", () => {
      const { roll, track } = renderOverview();
      fireEvent.pointerDown(track, { clientX: 300, button: 0 }); // park the window at 75 %
      expect(roll.scrollLeft).toBe(210);

      fireEvent.pointerDown(track, { clientX: 300, button: 0 }); // grab its middle
      expect(roll.scrollLeft).toBe(210);
      fireEvent.pointerMove(window, { clientX: 260 }); // 65 % of the clip
      expect(roll.scrollLeft).toBe(172);
      fireEvent.pointerUp(window);

      fireEvent.pointerMove(window, { clientX: 100 });
      expect(roll.scrollLeft).toBe(172);
    });

    it("pans from the keyboard so the strip is a real slider", () => {
      const { roll, track, onChangeNotes } = renderOverview();
      track.focus();

      fireEvent.keyDown(track, { key: "ArrowRight" });
      expect(roll.scrollLeft).toBe(39); // a quarter of the 156 px viewport
      fireEvent.keyDown(track, { key: "End" });
      expect(roll.scrollLeft).toBe(228); // 384 − 156
      expect(track.getAttribute("aria-valuenow")).toBe("100");
      fireEvent.keyDown(track, { key: "Home" });
      expect(roll.scrollLeft).toBe(0);
      expect(track.getAttribute("aria-valuenow")).toBe("0");

      // The overview's keys never reach the note selection.
      expect(onChangeNotes).not.toHaveBeenCalled();
    });

    it("zooms from the strip and keeps the window truthful", () => {
      const { container, roll, track, windowEl } = renderOverview();
      const grid = container.querySelector(".se-midi-grid") as HTMLElement;

      fireEvent.click(screen.getByLabelText("Zoom in the piano roll"));
      expect(parseFloat(grid.style.width)).toBe(576);
      // 156 of 576 px → 27.1 %, with the old centre still in the middle.
      expect(parseFloat(windowEl.style.width)).toBeCloseTo((156 / 576) * 100, 2);
      expect(roll.scrollLeft).toBe(39);
      expect(parseFloat(windowEl.style.left)).toBeCloseTo((39 / 576) * 100, 2);

      fireEvent.doubleClick(track, { clientX: 300 }); // zoom around 75 % of the clip
      expect(parseFloat(grid.style.width)).toBe(864);
      expect(roll.scrollLeft).toBe(570); // 0.75 × 864 − 78

      fireEvent.click(screen.getByLabelText("Zoom out the piano roll"));
      expect(parseFloat(grid.style.width)).toBe(576);
    });
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

    it("edits velocity and position from the velocity lane keys", () => {
      const { section, container, onChangeNotes } = renderWithNotes();
      const lane = container.querySelector(".se-midi-velocity") as HTMLElement;
      selectAll(section);

      fireEvent.keyDown(lane, { key: "ArrowUp" });
      const louder = onChangeNotes.mock.calls.at(-1)?.[0] as MidiNote[];
      expect(louder.map((note) => note.velocity)).toEqual([101, 101]);

      fireEvent.keyDown(lane, { key: "ArrowDown", shiftKey: true });
      const quieter = onChangeNotes.mock.calls.at(-1)?.[0] as MidiNote[];
      expect(quieter.map((note) => note.velocity)).toEqual([90, 90]);

      fireEvent.keyDown(lane, { key: "ArrowRight" });
      const moved = onChangeNotes.mock.calls.at(-1)?.[0] as MidiNote[];
      expect(moved[0].start).toBeCloseTo(0.35, 6);
      expect(moved[0].velocity).toBe(100);
    });

    it("toggles musical typing with Ctrl K so Z stops zooming", () => {
      const { section, container } = renderWithNotes();
      const gridWidth = () =>
        Number.parseFloat((container.querySelector(".se-midi-grid") as HTMLElement).style.width);
      const keys = () => screen.getByRole("button", { name: /^Keys (On|Off)$/ });

      expect(keys().getAttribute("aria-pressed")).toBe("false");
      selectAll(section);

      // Keys off: Z zooms the roll to the selection.
      const fit = gridWidth();
      fireEvent.keyDown(section, { key: "z" });
      const zoomed = gridWidth();
      expect(zoomed).toBeGreaterThan(fit);

      // Keys on: Z moves the playable octave instead of zooming.
      fireEvent.keyDown(section, { key: "k", ctrlKey: true });
      expect(keys().getAttribute("aria-pressed")).toBe("true");
      fireEvent.keyDown(section, { key: "z" });
      expect(gridWidth()).toBe(zoomed);
      fireEvent.keyDown(section, { key: "x" });
      expect(gridWidth()).toBe(zoomed);

      // The control bar toggles the same mode.
      fireEvent.click(keys());
      expect(keys().getAttribute("aria-pressed")).toBe("false");
    });

    it("zooms the grid with Ctrl = / Ctrl - and Z fits the selection", () => {
      const { section, container } = renderWithNotes();
      const gridWidth = () =>
        Number.parseFloat((container.querySelector(".se-midi-grid") as HTMLElement).style.width);
      const fit = gridWidth();

      fireEvent.keyDown(section, { key: "=", ctrlKey: true });
      expect(gridWidth()).toBeGreaterThan(fit);
      fireEvent.keyDown(section, { key: "-", ctrlKey: true });
      expect(gridWidth()).toBeCloseTo(fit, 5);

      selectAll(section);
      fireEvent.keyDown(section, { key: "z" });
      expect(gridWidth()).toBeGreaterThan(fit);

      // Nothing selected: Z goes back to the whole clip.
      fireEvent.keyDown(section, { key: "Escape" });
      fireEvent.keyDown(section, { key: "z" });
      expect(gridWidth()).toBeCloseTo(fit, 5);
    });

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
