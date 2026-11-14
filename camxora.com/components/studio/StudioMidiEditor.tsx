"use client";

import { useEffect, useRef, useState } from "react";

import { Icon } from "@/components/Icon";
import {
  buildMidiChordNotes,
  sanitizePoints,
  MIDI_MAX_PITCH,
  MIDI_MIN_PITCH,
  MIDI_PITCHES,
  MIDI_ROW,
  isBlackKey,
  noteName,
  playablePitch,
  scheduleMidiNote,
  type MidiArpMode,
  type MidiChordMode,
  type MidiInstrument,
  type MidiNote,
  type MidiPoint,
} from "@/lib/studio-midi";

/**
 * MIDI clip editor (S31/S64): piano gutter, note grid, velocity lane and the captured
 * control bar. Notes are edited in place and written through the clip document, so undo
 * and persistence work like audio clips. Pitch bend/modulation lanes were captured but
 * have no model yet, so those tabs are disabled with a reason rather than faked.
 */

export type StudioMidiEditorProps = {
  clip: {
    id: string;
    title?: string;
    duration?: number;
    color?: string;
    midi?: {
      notes?: MidiNote[];
      bend?: MidiPoint[];
      mod?: MidiPoint[];
    };
  };
  barWidth: number;
  secondsPerBar: number;
  loop: boolean;
  keyName: string;
  scaleName: string;
  onKeyChange: (key: string) => void;
  onScaleChange: (scale: string) => void;
  instrument: MidiInstrument;
  onInstrumentChange: (instrument: MidiInstrument) => void;
  /** N-14: designed wavetables available to this project. */
  wavetables?: Array<{ id: string; name: string }>;
  /** Opens the Wavetable Designer; hidden when advanced content is off. */
  onDesignWavetable?: () => void;
  onImportMidi: (file: File) => void;
  onToggleLoop: () => void;
  onChangeNotes: (notes: MidiNote[]) => void;
  onChangeLanes: (lane: "bend" | "mod", points: MidiPoint[]) => void;
  onClose: () => void;
};

const KEYS = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"];
/** MIDI grid zoom: 1 is the whole clip fitted to the panel, 12 is the closest. */
const ZOOM_MIN = 1;
const ZOOM_MAX = 12;
const ZOOM_STEP = 1.5;
const SCALES: Record<string, number[]> = {
  major: [0, 2, 4, 5, 7, 9, 11],
  minor: [0, 2, 3, 5, 7, 8, 10],
};

function inScale(pitch: number, keyName: string, scaleName: string): boolean {
  const scale = SCALES[scaleName];
  if (!scale) return true;
  const root = KEYS.indexOf(keyName);
  if (root < 0) return true;
  return scale.includes((((pitch - root) % 12) + 12) % 12);
}

function snapToScale(pitch: number, keyName: string, scaleName: string): number {
  if (inScale(pitch, keyName, scaleName)) return pitch;
  for (let offset = 1; offset <= 6; offset += 1) {
    if (inScale(pitch - offset, keyName, scaleName)) return pitch - offset;
    if (inScale(pitch + offset, keyName, scaleName)) return pitch + offset;
  }
  return pitch;
}

type DragState = {
  id: string;
  startX: number;
  startY: number;
  origin: MidiNote;
  notes: MidiNote[];
};

export function StudioMidiEditor(props: StudioMidiEditorProps) {
  const {
    clip,
    barWidth,
    secondsPerBar,
    loop,
    keyName,
    scaleName,
    onKeyChange,
    onScaleChange,
    instrument,
    onInstrumentChange,
    wavetables = [],
    onDesignWavetable,
    onImportMidi,
    onToggleLoop,
    onChangeNotes,
    onChangeLanes,
    onClose,
  } = props;
  const notes = clip.midi?.notes ?? [];
  const duration = Math.max(0.5, clip.duration ?? secondsPerBar * 4);
  /** Width of one clip at the fit zoom; the panel's zoom multiplies it. */
  const fitWidth = Math.max(96, (duration / secondsPerBar) * barWidth);
  const rollHeight = MIDI_PITCHES * MIDI_ROW;
  const [zoom, setZoom] = useState(1);
  const width = Math.max(96, Math.round(fitWidth * zoom));
  const [quantize, setQuantize] = useState<"4" | "8" | "16">("8");
  const [chordMode, setChordMode] = useState<MidiChordMode>("off");
  const [arpMode, setArpMode] = useState<MidiArpMode>("off");
  const [lane, setLane] = useState<"velocity" | "bend" | "mod">("velocity");
  const [drag, setDrag] = useState<DragState | null>(null);
  const [preview, setPreview] = useState<MidiNote | null>(null);
  const [velocityDrag, setVelocityDrag] = useState<{ id: string; notes: MidiNote[] } | null>(null);
  const [velocityPreview, setVelocityPreview] = useState<number | null>(null);
  /** Notes targeted by the keyboard actions (Ctrl A / arrows / Q / 0 / Delete). */
  const [selectedIds, setSelectedIds] = useState<Set<string>>(() => new Set());
  /**
   * CTRL K: musical typing. While on, the `A`–`;` row auditions notes and `Z`/`X`,
   * `C`/`V` move the octave and velocity. Off by default so the zoom and clipboard
   * letters keep working.
   */
  const [keysMode, setKeysMode] = useState(false);
  const [keysOctave, setKeysOctave] = useState(4);
  const [keysVelocity, setKeysVelocity] = useState(100);
  const auditionRef = useRef<AudioContext | null>(null);
  const rollRef = useRef<HTMLDivElement | null>(null);
  const sectionRef = useRef<HTMLElement | null>(null);
  const midiFileRef = useRef<HTMLInputElement | null>(null);

  // Start around middle C, like the capture.
  useEffect(() => {
    const element = rollRef.current;
    if (!element) return;
    element.scrollTop = Math.max(0, (MIDI_MAX_PITCH - 72) * MIDI_ROW - 24);
  }, [clip.id]);

  // The panel owns its shortcuts while it is open; focus it on arrival so the
  // keys do not fall through to the arrangement's global bindings. The frame
  // delay matters: the click that opened the panel would otherwise steal focus
  // back to the clip once its default action runs.
  useEffect(() => {
    const frame = requestAnimationFrame(() => sectionRef.current?.focus());
    return () => cancelAnimationFrame(frame);
  }, [clip.id]);

  // A different clip starts with nothing selected.
  useEffect(() => {
    setSelectedIds(new Set());
    setZoom(1);
  }, [clip.id]);

  const step = secondsPerBar / Number(quantize);

  const timeAt = (clientX: number, grid: HTMLElement) => {
    const rect = grid.getBoundingClientRect();
    const seconds = ((clientX - rect.left) / width) * duration;
    return Math.max(0, Math.min(duration, Math.round(seconds / step) * step));
  };

  const pitchAt = (clientY: number, grid: HTMLElement) => {
    const rect = grid.getBoundingClientRect();
    const row = Math.floor((clientY - rect.top) / MIDI_ROW);
    return Math.max(MIDI_MIN_PITCH, Math.min(MIDI_MAX_PITCH, MIDI_MAX_PITCH - row));
  };

  function addNote(event: React.PointerEvent<HTMLDivElement>) {
    if (event.button !== 0) return;
    const grid = event.currentTarget;
    const start = timeAt(event.clientX, grid);
    const pitch = snapToScale(pitchAt(event.clientY, grid), keyName, scaleName);
    const created = buildMidiChordNotes({
      pitch,
      chordMode,
      arpMode,
      start,
      step,
      baseLength: Math.min(duration - start, Math.max(step, secondsPerBar / 4)),
      duration,
    });
    if (!created.length) return;
    const stamp = `${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 5)}`;
    const additions: MidiNote[] = created.map((note, index) => ({
      ...note,
      id: `note-${stamp}-${index}`,
      velocity: 100,
    }));
    // Clicking the same cell twice should not stack duplicate notes.
    const fresh = additions.filter(
      (note) =>
        !notes.some(
          (existing) =>
            existing.pitch === note.pitch && Math.abs(existing.start - note.start) < 0.005
        )
    );
    if (fresh.length) {
      onChangeNotes([...notes, ...fresh]);
      setSelectedIds(new Set(fresh.map((note) => note.id)));
      sectionRef.current?.focus();
    }
  }

  function startDrag(event: React.PointerEvent<HTMLButtonElement>, note: MidiNote) {
    event.stopPropagation();
    if (event.button !== 0) return;
    const additive = event.shiftKey || event.ctrlKey || event.metaKey;
    setSelectedIds((current) => {
      const next = new Set(additive ? current : []);
      if (additive && next.has(note.id)) next.delete(note.id);
      else next.add(note.id);
      return next;
    });
    setDrag({
      id: note.id,
      startX: event.clientX,
      startY: event.clientY,
      origin: note,
      notes,
    });
    setPreview(note);
  }

  useEffect(() => {
    if (!drag) return;
    const onMove = (event: PointerEvent) => {
      const dx = event.clientX - drag.startX;
      const dy = event.clientY - drag.startY;
      const deltaTime = Math.round((dx / width) * duration / step) * step;
      const deltaPitch = -Math.round(dy / MIDI_ROW);
      setPreview({
        ...drag.origin,
        start: Math.max(0, Math.min(duration - drag.origin.length, drag.origin.start + deltaTime)),
        pitch: Math.max(
          MIDI_MIN_PITCH,
          Math.min(MIDI_MAX_PITCH, drag.origin.pitch + deltaPitch)
        ),
      });
    };
    const onUp = () => {
      if (drag && preview) {
        onChangeNotes(
          drag.notes.map((note) => (note.id === drag.id ? { ...preview } : note))
        );
      }
      setDrag(null);
      setPreview(null);
    };
    window.addEventListener("pointermove", onMove);
    window.addEventListener("pointerup", onUp);
    return () => {
      window.removeEventListener("pointermove", onMove);
      window.removeEventListener("pointerup", onUp);
    };
  }, [drag, preview, width, duration, step, onChangeNotes]);

  useEffect(() => {
    if (!velocityDrag) return;
    const onMove = (event: PointerEvent) => {
      const lane = document.querySelector(".se-midi-velocity");
      if (!(lane instanceof HTMLElement)) return;
      const rect = lane.getBoundingClientRect();
      const ratio = 1 - (event.clientY - rect.top) / rect.height;
      setVelocityPreview(Math.max(1, Math.min(127, Math.round(ratio * 127))));
    };
    const onUp = () => {
      // A state updater has to stay pure: writing the parent's document from inside
      // one updates another component while React is rendering this one.
      if (velocityDrag && velocityPreview !== null) {
        onChangeNotes(
          velocityDrag.notes.map((note) =>
            note.id === velocityDrag.id ? { ...note, velocity: velocityPreview } : note
          )
        );
      }
      setVelocityDrag(null);
      setVelocityPreview(null);
    };
    window.addEventListener("pointermove", onMove);
    window.addEventListener("pointerup", onUp);
    return () => {
      window.removeEventListener("pointermove", onMove);
      window.removeEventListener("pointerup", onUp);
    };
  }, [velocityDrag, velocityPreview, onChangeNotes]);

  function transposeNotes(delta: number) {
    onChangeNotes(
      notes.map((note) => ({
        ...note,
        pitch: Math.max(MIDI_MIN_PITCH, Math.min(MIDI_MAX_PITCH, note.pitch + delta)),
      }))
    );
  }

  const shown = preview
    ? notes.map((note) => (note.id === preview.id ? preview : note))
    : velocityPreview !== null && velocityDrag
      ? notes.map((note) =>
          note.id === velocityDrag.id ? { ...note, velocity: velocityPreview } : note
        )
      : notes;

  /** Zoom the grid around the fit width (S14: CTRL = / CTRL -). */
  function zoomBy(factor: number) {
    setZoom((current) =>
      Math.min(ZOOM_MAX, Math.max(ZOOM_MIN, Number((current * factor).toFixed(2))))
    );
  }

  /**
   * S14 "zoom to selection": fit the selected notes into the roll, then scroll so
   * they start on the left. With nothing selected it goes back to the whole clip.
   */
  function zoomToSelection() {
    const selected = notes.filter((note) => selectedIds.has(note.id));
    if (!selected.length) {
      setZoom(ZOOM_MIN);
      requestAnimationFrame(() => {
        if (rollRef.current) rollRef.current.scrollLeft = 0;
      });
      return;
    }
    const start = Math.min(...selected.map((note) => note.start));
    const end = Math.max(...selected.map((note) => note.start + note.length));
    const span = Math.max(0.05, end - start);
    const viewport = Math.max(96, (rollRef.current?.clientWidth ?? 460) - 44);
    const pixelsPerSecond = fitWidth / duration;
    const target = Math.min(ZOOM_MAX, Math.max(ZOOM_MIN, (viewport * 0.9) / (span * pixelsPerSecond)));
    setZoom(Number(target.toFixed(2)));
    requestAnimationFrame(() => {
      const roll = rollRef.current;
      if (!roll) return;
      roll.scrollLeft = Math.max(0, (start / duration) * fitWidth * target - 24);
    });
  }

  /** Audition one pitch through the same synth voice the transport uses. */
  function auditionPitch(pitch: number) {
    const Context =
      typeof window !== "undefined"
        ? window.AudioContext ??
          (window as unknown as { webkitAudioContext?: typeof AudioContext }).webkitAudioContext
        : undefined;
    if (!Context) return;
    auditionRef.current ??= new Context();
    const context = auditionRef.current;
    void context.resume();
    scheduleMidiNote(
      context,
      context.destination,
      {
        id: `audition-${pitch}`,
        pitch,
        start: 0,
        length: 0.35,
        velocity: keysVelocity,
      },
      context.currentTime
    );
  }

  /**
   * Reference shortcut map (S14, CLIP EDITOR – MIDI): Ctrl A selects every note,
   * Shift Q quantizes, 0 toggles the disabled state, arrows nudge/transpose,
   * Delete removes, Shift 1 / Shift 2 set the grid and Ctrl =/- / Z zoom.
   */
  function handleKeyDown(event: React.KeyboardEvent<HTMLElement>) {
    const target = event.target as HTMLElement | null;
    if (target?.closest("input, textarea, select, [contenteditable='true']")) return;

    const mod = event.metaKey || event.ctrlKey;
    if (mod && event.key.toLowerCase() === "k") {
      event.preventDefault();
      event.stopPropagation();
      setKeysMode((on) => !on);
      return;
    }
    if (keysMode && !mod && !event.altKey) {
      const letter = event.key.toLowerCase();
      if (letter === "z" || letter === "x") {
        event.preventDefault();
        event.stopPropagation();
        setKeysOctave((octave) =>
          Math.max(0, Math.min(8, octave + (letter === "x" ? 1 : -1)))
        );
        return;
      }
      if (letter === "c" || letter === "v") {
        event.preventDefault();
        event.stopPropagation();
        setKeysVelocity((velocity) =>
          Math.max(1, Math.min(127, velocity + (letter === "v" ? 10 : -10)))
        );
        return;
      }
      const pitch = playablePitch(letter, keysOctave);
      if (pitch !== null) {
        event.preventDefault();
        event.stopPropagation();
        auditionPitch(pitch);
        return;
      }
    }
    if (mod && (event.key === "=" || event.key === "+")) {
      event.preventDefault();
      event.stopPropagation();
      zoomBy(ZOOM_STEP);
      return;
    }
    if (mod && (event.key === "-" || event.key === "_")) {
      event.preventDefault();
      event.stopPropagation();
      zoomBy(1 / ZOOM_STEP);
      return;
    }
    if (!mod && !event.altKey && event.key.toLowerCase() === "z") {
      event.preventDefault();
      event.stopPropagation();
      zoomToSelection();
      return;
    }
    if (mod && event.key.toLowerCase() === "a") {
      event.preventDefault();
      event.stopPropagation();
      setSelectedIds(new Set(notes.map((note) => note.id)));
      return;
    }

    const denser = event.shiftKey && (event.key === "1" || event.key === "!");
    const sparser = event.shiftKey && (event.key === "2" || event.key === "@");
    if (denser || sparser) {
      event.preventDefault();
      event.stopPropagation();
      setQuantize((current) =>
        denser ? (current === "4" ? "8" : "16") : current === "16" ? "8" : "4"
      );
      return;
    }

    if (event.key === "Escape") {
      if (selectedIds.size) {
        event.stopPropagation();
        setSelectedIds(new Set());
      }
      return;
    }

    const selected = notes.filter((note) => selectedIds.has(note.id));
    if (!selected.length) return;
    const ids = new Set(selected.map((note) => note.id));
    const patchSelected = (patch: (note: MidiNote) => Partial<MidiNote>) => {
      event.preventDefault();
      event.stopPropagation();
      onChangeNotes(notes.map((note) => (ids.has(note.id) ? { ...note, ...patch(note) } : note)));
    };

    if (event.key === "ArrowLeft" || event.key === "ArrowRight") {
      const delta = (event.key === "ArrowRight" ? 1 : -1) * step;
      if (event.shiftKey) {
        // Shift ↔ lengthens/shortens, as the captured map does.
        patchSelected((note) => ({
          length: Math.max(
            0.02,
            Math.min(Math.max(0.02, duration - note.start), note.length + delta)
          ),
        }));
        return;
      }
      patchSelected((note) => ({
        start: Math.max(0, Math.min(Math.max(0, duration - note.length), note.start + delta)),
      }));
      return;
    }
    if (event.key === "ArrowUp" || event.key === "ArrowDown") {
      const amount = (event.key === "ArrowUp" ? 1 : -1) * (event.shiftKey ? 12 : 1);
      patchSelected((note) => ({
        pitch: Math.max(MIDI_MIN_PITCH, Math.min(MIDI_MAX_PITCH, note.pitch + amount)),
      }));
      return;
    }
    if (event.key === "Backspace" || event.key === "Delete") {
      event.preventDefault();
      event.stopPropagation();
      onChangeNotes(notes.filter((note) => !ids.has(note.id)));
      setSelectedIds(new Set());
      return;
    }
    if (event.key === "0") {
      const disable = selected.some((note) => !note.disabled);
      patchSelected(() => (disable ? { disabled: true } : { disabled: undefined }));
      return;
    }
    if (event.shiftKey && event.key.toLowerCase() === "q") {
      patchSelected((note) => ({ start: Math.max(0, Math.round(note.start / step) * step) }));
    }
  }

  /**
   * S14 velocity lane: ←/→ move the selected notes, ↑/↓ change their velocity.
   * The lane takes focus on press so these never reach the arrangement.
   */
  function handleVelocityKeys(event: React.KeyboardEvent<HTMLDivElement>) {
    if (event.metaKey || event.ctrlKey || event.altKey) return;
    const selected = notes.filter((note) => selectedIds.has(note.id));
    if (!selected.length) return;
    const ids = new Set(selected.map((note) => note.id));
    if (event.key === "ArrowUp" || event.key === "ArrowDown") {
      event.preventDefault();
      event.stopPropagation();
      const delta = (event.key === "ArrowUp" ? 1 : -1) * (event.shiftKey ? 10 : 1);
      onChangeNotes(
        notes.map((note) =>
          ids.has(note.id)
            ? { ...note, velocity: Math.max(1, Math.min(127, note.velocity + delta)) }
            : note
        )
      );
      return;
    }
    if (event.key === "ArrowLeft" || event.key === "ArrowRight") {
      event.preventDefault();
      event.stopPropagation();
      const delta = (event.key === "ArrowRight" ? 1 : -1) * step;
      onChangeNotes(
        notes.map((note) =>
          ids.has(note.id)
            ? {
                ...note,
                start: Math.max(
                  0,
                  Math.min(Math.max(0, duration - note.length), note.start + delta)
                ),
              }
            : note
        )
      );
    }
  }

  return (
    <>
    <section
      className="se-midi"
      aria-label="MIDI editor"
      ref={sectionRef}
      tabIndex={-1}
      onKeyDown={handleKeyDown}
    >
      <header className="se-midi-head">
        <strong>{clip.title || "MIDI clip"}</strong>
        <button type="button" className="se-icon" aria-label="Close MIDI editor" onClick={onClose}>
          <Icon name="fa-xmark" />
        </button>
      </header>

      <div className="se-midi-tabs" role="tablist" aria-label="MIDI lanes">
        {(
          [
            ["velocity", "Velocity"],
            ["bend", "Pitch Bend"],
            ["mod", "Modulation"],
          ] as const
        ).map(([value, label]) => (
          <button
            key={value}
            type="button"
            role="tab"
            aria-selected={lane === value}
            className={lane === value ? "on" : ""}
            onClick={() => setLane(value)}
          >
            {label}
          </button>
        ))}
      </div>

      <div className="se-midi-roll" ref={rollRef}>
        <div className="se-midi-keys" aria-hidden="true">
          {Array.from({ length: MIDI_PITCHES }).map((_, index) => {
            const pitch = MIDI_MAX_PITCH - index;
            const label = pitch % 12 === 0 ? noteName(pitch) : "";
            return (
              <span
                key={pitch}
                className={`se-midi-key${isBlackKey(pitch) ? " black" : ""}`}
                style={{ height: MIDI_ROW }}
              >
                {label}
              </span>
            );
          })}
        </div>
        <div
          className="se-midi-grid"
          style={{ width, height: rollHeight }}
          onPointerDown={addNote}
        >
          {Array.from({ length: MIDI_PITCHES }).map((_, index) => {
            const pitch = MIDI_MAX_PITCH - index;
            return (
              <span
                key={pitch}
                className={`se-midi-row${isBlackKey(pitch) ? " black" : ""}${
                  inScale(pitch, keyName, scaleName) ? "" : " out"
                }`}
                style={{ top: index * MIDI_ROW, height: MIDI_ROW }}
                aria-hidden="true"
              />
            );
          })}
          {shown.map((note) => (
            <button
              key={note.id}
              type="button"
              className={`se-midi-note${selectedIds.has(note.id) ? " is-selected" : ""}${
                note.disabled ? " is-disabled" : ""
              }`}
              style={{
                left: (note.start / duration) * width,
                top: (MIDI_MAX_PITCH - note.pitch) * MIDI_ROW + 1,
                width: Math.max(6, (note.length / duration) * width),
                background: clip.color || "hsl(var(--accent))",
              }}
              aria-label={`Note ${noteName(note.pitch)} at ${note.start.toFixed(2)}s, velocity ${note.velocity}${
                note.disabled ? ", disabled" : ""
              }`}
              aria-pressed={selectedIds.has(note.id)}
              data-velocity={note.velocity}
              data-disabled={note.disabled ? "true" : undefined}
              onPointerDown={(event) => startDrag(event, note)}
              onDoubleClick={(event) => {
                event.stopPropagation();
                onChangeNotes(notes.filter((item) => item.id !== note.id));
              }}
            />
          ))}
        </div>
      </div>

      <div
        className="se-midi-velocity"
        role="group"
        tabIndex={0}
        onKeyDown={handleVelocityKeys}
        aria-label={lane === "velocity" ? "Velocity lane" : `${lane === "bend" ? "Pitch bend" : "Modulation"} lane`}
        onPointerDown={(event) => {
          // Keep the lane's own arrow keys (velocity / move) in the lane.
          event.currentTarget.focus();
          if (lane === "velocity") {
            const rect = event.currentTarget.getBoundingClientRect();
            const seconds = ((event.clientX - rect.left - 44) / width) * duration;
            const nearest = notes.reduce<MidiNote | null>((best, note) => {
              if (!best) return note;
              return Math.abs(note.start - seconds) < Math.abs(best.start - seconds) ? note : best;
            }, null);
            if (!nearest) return;
            const additive = event.shiftKey || event.ctrlKey || event.metaKey;
            setSelectedIds((current) => {
              const next = new Set(additive ? current : []);
              next.add(nearest.id);
              return next;
            });
            setVelocityDrag({ id: nearest.id, notes });
            const ratio = 1 - (event.clientY - rect.top) / rect.height;
            setVelocityPreview(Math.max(1, Math.min(127, Math.round(ratio * 127))));
            return;
          }
          const rect = event.currentTarget.getBoundingClientRect();
          const at = Math.min(
            duration,
            Math.max(0, ((event.clientX - rect.left - 44) / width) * duration)
          );
          const ratio = 1 - (event.clientY - rect.top) / rect.height;
          const value = lane === "bend" ? ratio * 2 - 1 : ratio;
          const points =
            lane === "bend"
              ? sanitizePoints(clip.midi?.bend, -1, 1)
              : sanitizePoints(clip.midi?.mod, 0, 1);
          const rounded = {
            at: Math.round(at * 100) / 100,
            value: Math.round(value * 100) / 100,
          };
          onChangeLanes(
            lane,
            [...points, rounded].sort((a, b) => a.at - b.at)
          );
        }}
      >
        {lane === "velocity" ? (
          <>
            <span className="se-midi-velocity-baseline" aria-hidden="true" />
            {shown.map((note) => {
              const height = Math.max(2, (note.velocity / 127) * 52);
              return (
                <span key={note.id}>
                  <span
                    className={`se-midi-velocity-bar${
                      velocityDrag?.id === note.id ? " is-active" : ""
                    }`}
                    style={{ left: 44 + (note.start / duration) * width, height }}
                  />
                  <span
                    className={`se-midi-velocity-dot${
                      velocityDrag?.id === note.id ? " is-active" : ""
                    }`}
                    style={{ left: 44 + (note.start / duration) * width + 1, bottom: 8 + height }}
                  />
                </span>
              );
            })}
          </>
        ) : (
          <svg
            className="se-midi-lane-svg"
            viewBox={`0 0 ${44 + width} 64`}
            preserveAspectRatio="none"
            aria-hidden="true"
          >
            <line
              x1={44}
              x2={44 + width}
              y1={lane === "bend" ? 32 : 60}
              y2={lane === "bend" ? 32 : 60}
              className="se-midi-lane-base"
            />
            {(() => {
              const points =
                lane === "bend"
                  ? sanitizePoints(clip.midi?.bend, -1, 1)
                  : sanitizePoints(clip.midi?.mod, 0, 1);
              const px = (point: { at: number }) => 44 + (point.at / duration) * width;
              const py = (point: { value: number }) =>
                lane === "bend" ? 32 - point.value * 28 : 60 - point.value * 52;
              return (
                <>
                  {points.length > 1 ? (
                    <polyline
                      className="se-midi-lane-line"
                      points={points.map((point) => `${px(point)},${py(point)}`).join(" ")}
                    />
                  ) : null}
                  {points.map((point, index) => (
                    <circle
                      key={`${point.at}-${index}`}
                      className="se-midi-lane-point"
                      cx={px(point)}
                      cy={py(point)}
                      r={3}
                      onPointerDown={(event) => event.stopPropagation()}
                      onDoubleClick={(event) => {
                        event.stopPropagation();
                        onChangeLanes(
                          lane,
                          points.filter((_, item) => item !== index)
                        );
                      }}
                    />
                  ))}
                </>
              );
            })()}
          </svg>
        )}
      </div>

      <div className="se-midi-controls">
        <button
          type="button"
          className={`se-midi-power${loop ? " on" : ""}`}
          aria-pressed={loop}
          aria-label="Loop"
          onClick={onToggleLoop}
        >
          <Icon name="fa-power-off" />
        </button>
        <span className="se-midi-control">
          Loop <strong>{loop ? "On" : "Off"}</strong>
        </span>
        <label className="se-midi-control">
          Quantize
          <select
            aria-label="Quantize"
            value={quantize}
            onChange={(event) => {
              const value = event.target.value as "4" | "8" | "16";
              setQuantize(value);
              // S31 applies the grid as soon as it is chosen (no Apply control).
              onChangeNotes(quantizeNotesLocal(notes, secondsPerBar / Number(value)));
            }}
          >
            <option value="4">1/4</option>
            <option value="8">1/8</option>
            <option value="16">1/16</option>
          </select>
        </label>
        <label className="se-midi-control">
          Instrument
          <select
            aria-label="MIDI instrument"
            value={instrument}
            onChange={(event) => onInstrumentChange(event.target.value as MidiInstrument)}
          >
            <option value="triangle">Triangle</option>
            <option value="sine">Sine</option>
            <option value="sawtooth">Saw</option>
            {wavetables.map((table) => (
              <option key={table.id} value={`wavetable:${table.id}`}>
                {table.name}
              </option>
            ))}
          </select>
        </label>
        {onDesignWavetable ? (
          <button
            type="button"
            className="se-pill se-midi-design"
            aria-label="Design a wavetable"
            onClick={onDesignWavetable}
          >
            <Icon name="fa-wave-square" /> Design wavetable
          </button>
        ) : null}
        <label className="se-midi-control">
          Chord
          <select
            aria-label="Chord mode"
            value={chordMode}
            onChange={(event) => setChordMode(event.target.value as MidiChordMode)}
          >
            <option value="off">Single note</option>
            <option value="major">Major</option>
            <option value="minor">Minor</option>
          </select>
        </label>
        <label className="se-midi-control">
          Arp
          <select
            aria-label="Arpeggiator"
            value={arpMode}
            onChange={(event) => setArpMode(event.target.value as MidiArpMode)}
          >
            <option value="off">Off</option>
            <option value="up">Up</option>
            <option value="down">Down</option>
          </select>
        </label>
        <label className="se-midi-control">
          Key
          <select aria-label="Key" value={keyName} onChange={(event) => onKeyChange(event.target.value)}>
            {KEYS.map((key) => (
              <option key={key} value={key}>
                {key} Maj
              </option>
            ))}
          </select>
        </label>
        <label className="se-midi-control">
          Scale
          <select
            aria-label="Scale"
            value={scaleName}
            onChange={(event) => onScaleChange(event.target.value)}
          >
            <option value="off">Off</option>
            <option value="major">Major</option>
            <option value="minor">Minor</option>
          </select>
        </label>
        <button
          type="button"
          className="se-pill"
          aria-label="Transpose MIDI down one octave"
          onClick={() => transposeNotes(-12)}
        >
          -12
        </button>
        <button
          type="button"
          className="se-pill"
          aria-label="Transpose MIDI up one octave"
          onClick={() => transposeNotes(12)}
        >
          +12
        </button>
        <button type="button" className="se-pill" onClick={() => onChangeNotes([])}>
          Clear
        </button>
        <input
          ref={midiFileRef}
          type="file"
          accept=".mid,.midi,audio/midi,audio/x-midi"
          hidden
          onChange={(event) => {
            const file = event.target.files?.[0];
            if (file) onImportMidi(file);
            event.target.value = "";
          }}
        />
        <button
          type="button"
          className="se-pill"
          onClick={() => midiFileRef.current?.click()}
        >
          Import MIDI
        </button>
        <button
          type="button"
          className={`se-pill${keysMode ? " on" : ""}`}
          aria-pressed={keysMode}
          title="Play notes with A–;, Z/X octave, C/V velocity (Ctrl K)"
          onClick={() => setKeysMode((on) => !on)}
        >
          Keys {keysMode ? "On" : "Off"}
        </button>
        <span className="se-midi-control">View All</span>
      </div>
    </section>
    </>
  );
}

/** Local copy so the component does not pull the whole midi lib into the render path. */
function quantizeNotesLocal(notes: MidiNote[], step: number): MidiNote[] {
  if (!(step > 0)) return notes;
  return notes.map((note) => ({ ...note, start: Math.round(note.start / step) * step }));
}
