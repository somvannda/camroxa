"use client";

import { useEffect, useRef, useState } from "react";

import { Icon } from "@/components/Icon";
import {
  MIDI_MAX_PITCH,
  MIDI_MIN_PITCH,
  MIDI_PITCHES,
  MIDI_ROW,
  isBlackKey,
  noteName,
  type MidiNote,
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
    midi?: { notes?: MidiNote[] };
  };
  barWidth: number;
  secondsPerBar: number;
  loop: boolean;
  keyName: string;
  scaleName: string;
  onKeyChange: (key: string) => void;
  onScaleChange: (scale: string) => void;
  onToggleLoop: () => void;
  onChangeNotes: (notes: MidiNote[]) => void;
  onClose: () => void;
};

const KEYS = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"];
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
    onToggleLoop,
    onChangeNotes,
    onClose,
  } = props;
  const notes = clip.midi?.notes ?? [];
  const duration = Math.max(0.5, clip.duration ?? secondsPerBar * 4);
  const width = Math.max(96, (duration / secondsPerBar) * barWidth);
  const rollHeight = MIDI_PITCHES * MIDI_ROW;
  const [quantize, setQuantize] = useState<"4" | "8" | "16">("8");
  const [drag, setDrag] = useState<DragState | null>(null);
  const [preview, setPreview] = useState<MidiNote | null>(null);
  const [velocityDrag, setVelocityDrag] = useState<{ id: string; notes: MidiNote[] } | null>(null);
  const [velocityPreview, setVelocityPreview] = useState<number | null>(null);
  const rollRef = useRef<HTMLDivElement | null>(null);

  // Start around middle C, like the capture.
  useEffect(() => {
    const element = rollRef.current;
    if (!element) return;
    element.scrollTop = Math.max(0, (MIDI_MAX_PITCH - 72) * MIDI_ROW - 24);
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
    const note: MidiNote = {
      id: `note-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 5)}`,
      pitch,
      start,
      length: Math.min(duration - start, Math.max(step, secondsPerBar / 4)),
      velocity: 100,
    };
    if (note.length < 0.02) return;
    onChangeNotes([...notes, note]);
  }

  function startDrag(event: React.PointerEvent<HTMLButtonElement>, note: MidiNote) {
    event.stopPropagation();
    if (event.button !== 0) return;
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
      setDrag((current) => {
        if (current && preview) {
          onChangeNotes(
            current.notes.map((note) => (note.id === current.id ? { ...preview } : note))
          );
        }
        return null;
      });
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
      setVelocityDrag((current) => {
        if (current && velocityPreview !== null) {
          onChangeNotes(
            current.notes.map((note) =>
              note.id === current.id ? { ...note, velocity: velocityPreview } : note
            )
          );
        }
        return null;
      });
      setVelocityPreview(null);
    };
    window.addEventListener("pointermove", onMove);
    window.addEventListener("pointerup", onUp);
    return () => {
      window.removeEventListener("pointermove", onMove);
      window.removeEventListener("pointerup", onUp);
    };
  }, [velocityDrag, velocityPreview, onChangeNotes]);

  const shown = preview
    ? notes.map((note) => (note.id === preview.id ? preview : note))
    : velocityPreview !== null && velocityDrag
      ? notes.map((note) =>
          note.id === velocityDrag.id ? { ...note, velocity: velocityPreview } : note
        )
      : notes;

  return (
    <section className="se-midi" aria-label="MIDI editor">
      <header className="se-midi-head">
        <strong>{clip.title || "MIDI clip"}</strong>
        <button type="button" className="se-icon" aria-label="Close MIDI editor" onClick={onClose}>
          <Icon name="fa-xmark" />
        </button>
      </header>

      <div className="se-midi-tabs" role="tablist" aria-label="MIDI lanes">
        <button type="button" role="tab" aria-selected className="on">
          Velocity
        </button>
        <button type="button" role="tab" aria-selected={false} disabled title="Pitch bend has no model yet">
          Pitch Bend
        </button>
        <button type="button" role="tab" aria-selected={false} disabled title="Modulation has no model yet">
          Modulation
        </button>
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
              className="se-midi-note"
              style={{
                left: (note.start / duration) * width,
                top: (MIDI_MAX_PITCH - note.pitch) * MIDI_ROW + 1,
                width: Math.max(6, (note.length / duration) * width),
                background: clip.color || "hsl(var(--accent))",
              }}
              aria-label={`Note ${noteName(note.pitch)} at ${note.start.toFixed(2)}s, velocity ${note.velocity}`}
              data-velocity={note.velocity}
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
        aria-label="Velocity lane"
        onPointerDown={(event) => {
          const rect = event.currentTarget.getBoundingClientRect();
          const seconds = ((event.clientX - rect.left - 44) / width) * duration;
          const nearest = notes.reduce<MidiNote | null>((best, note) => {
            if (!best) return note;
            return Math.abs(note.start - seconds) < Math.abs(best.start - seconds) ? note : best;
          }, null);
          if (!nearest) return;
          setVelocityDrag({ id: nearest.id, notes });
          const ratio = 1 - (event.clientY - rect.top) / rect.height;
          setVelocityPreview(Math.max(1, Math.min(127, Math.round(ratio * 127))));
        }}
      >
        <span className="se-midi-velocity-baseline" aria-hidden="true" />
        {shown.map((note) => (
          <span
            key={note.id}
            className={`se-midi-velocity-bar${
              velocityDrag?.id === note.id ? " is-active" : ""
            }`}
            style={{
              left: 44 + (note.start / duration) * width,
              height: Math.max(2, (note.velocity / 127) * 52),
            }}
          />
        ))}
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
            }}
          >
            <option value="4">1/4</option>
            <option value="8">1/8</option>
            <option value="16">1/16</option>
          </select>
        </label>
        <button
          type="button"
          className="se-midi-apply"
          onClick={() => onChangeNotes(quantizeNotesLocal(notes, step))}
        >
          Apply
        </button>
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
        <span className="se-midi-control">View All</span>
      </div>
    </section>
  );
}

/** Local copy so the component does not pull the whole midi lib into the render path. */
function quantizeNotesLocal(notes: MidiNote[], step: number): MidiNote[] {
  if (!(step > 0)) return notes;
  return notes.map((note) => ({ ...note, start: Math.round(note.start / step) * step }));
}
