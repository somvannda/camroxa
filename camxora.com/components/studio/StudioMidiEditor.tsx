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
 *
 * Above the grid sits the captured overview strip: a mini piano roll for the whole clip,
 * a window for the visible slice, and zoom −/+ at the left. It is wired to the roll's real
 * horizontal scroll, so dragging it is the fast way to navigate a zoomed-in clip.
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
/** Width of the piano gutter; the overview and the lanes share it. */
const MIDI_GUTTER = 44;
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
  const overviewRef = useRef<HTMLDivElement | null>(null);
  /** The roll's real horizontal scroll, in grid pixels; the overview window mirrors it. */
  const [rollView, setRollView] = useState({ clientWidth: 0, scrollLeft: 0 });
  /** The clip point a zoom step should keep in place once the new width lands. */
  const zoomAnchor = useRef<{ ratio: number; viewport: number } | null>(null);
  const [overviewDrag, setOverviewDrag] = useState(false);
  /** Pointer offset inside the overview window, so grabbing it does not jump. */
  const overviewGrab = useRef(0);

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

  // A different clip starts with nothing selected, at the fit zoom, scrolled to the top left.
  useEffect(() => {
    setSelectedIds(new Set());
    setZoom(1);
    const roll = rollRef.current;
    if (roll) roll.scrollLeft = 0;
    setRollView((current) => (current.scrollLeft === 0 ? current : { ...current, scrollLeft: 0 }));
  }, [clip.id]);

  // The overview window is the roll's real viewport, so measure it and follow resizes.
  // `width` is a dependency because a zoom changes the scroll range without resizing
  // the panel itself, which a ResizeObserver alone would not report.
  useEffect(() => {
    const roll = rollRef.current;
    if (!roll) return;
    const measure = () => {
      setRollView((current) =>
        current.clientWidth === roll.clientWidth && current.scrollLeft === roll.scrollLeft
          ? current
          : { clientWidth: roll.clientWidth, scrollLeft: roll.scrollLeft }
      );
    };
    measure();
    if (typeof ResizeObserver === "undefined") {
      window.addEventListener("resize", measure);
      return () => window.removeEventListener("resize", measure);
    }
    const observer = new ResizeObserver(measure);
    observer.observe(roll);
    return () => observer.disconnect();
  }, [clip.id, width]);

  // A zoom step lands the anchored clip point back under the same viewport position, so
  // zooming keeps the part you were looking at instead of jumping to the clip start.
  useEffect(() => {
    const anchor = zoomAnchor.current;
    if (!anchor) return;
    zoomAnchor.current = null;
    const roll = rollRef.current;
    if (!roll) return;
    const view = Math.max(0, Math.min(width, roll.clientWidth - MIDI_GUTTER));
    const max = Math.max(0, width - view);
    roll.scrollLeft = Math.min(max, Math.max(0, anchor.ratio * width - anchor.viewport * view));
    setRollView({ clientWidth: roll.clientWidth, scrollLeft: roll.scrollLeft });
  }, [width]);

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

  /** Pull the roll's current scroll position into state (the overview renders from it). */
  function syncRollView() {
    const roll = rollRef.current;
    if (!roll) return;
    setRollView((current) =>
      current.clientWidth === roll.clientWidth && current.scrollLeft === roll.scrollLeft
        ? current
        : { clientWidth: roll.clientWidth, scrollLeft: roll.scrollLeft }
    );
  }

  /** Visible grid pixels: the roll's viewport minus the sticky piano gutter. */
  function visibleGridWidth(roll: HTMLDivElement | null = rollRef.current) {
    const client = roll?.clientWidth ?? 0;
    return Math.max(0, Math.min(width, client - MIDI_GUTTER));
  }

  function currentScrollLeft() {
    return rollRef.current?.scrollLeft ?? rollView.scrollLeft;
  }

  /** Scroll the roll to an absolute grid offset, clamped to the real scroll range. */
  function scrollToGrid(target: number) {
    const roll = rollRef.current;
    if (!roll) return;
    const max = Math.max(0, width - visibleGridWidth(roll));
    roll.scrollLeft = Math.min(max, Math.max(0, Math.round(target)));
    syncRollView();
  }

  /** Scroll so the given point of the clip (0–1) sits in the middle of the roll. */
  function scrollToRatio(ratio: number) {
    const clamped = Math.min(1, Math.max(0, ratio));
    scrollToGrid(clamped * width - visibleGridWidth() / 2);
  }

  /**
   * Change the zoom while keeping a point of the clip under the same place in the
   * viewport. The new width only exists after the next render, so the anchor is
   * consumed by the width effect above.
   */
  function applyZoom(next: number, anchorRatio?: number) {
    const clamped = Math.min(ZOOM_MAX, Math.max(ZOOM_MIN, Number(next.toFixed(2))));
    if (clamped === zoom) return;
    const view = visibleGridWidth();
    const ratio = anchorRatio ?? (currentScrollLeft() + view / 2) / width;
    zoomAnchor.current = {
      ratio: Math.min(1, Math.max(0, ratio)),
      viewport: 0.5,
    };
    setZoom(clamped);
  }

  /** Zoom the grid around the fit width (S14: CTRL = / CTRL -). */
  function zoomBy(factor: number) {
    applyZoom(zoom * factor);
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
        syncRollView();
      });
      return;
    }
    const start = Math.min(...selected.map((note) => note.start));
    const end = Math.max(...selected.map((note) => note.start + note.length));
    const span = Math.max(0.05, end - start);
    const viewport = Math.max(96, (rollRef.current?.clientWidth ?? 460) - MIDI_GUTTER);
    const pixelsPerSecond = fitWidth / duration;
    const target = Math.min(ZOOM_MAX, Math.max(ZOOM_MIN, (viewport * 0.9) / (span * pixelsPerSecond)));
    setZoom(Number(target.toFixed(2)));
    requestAnimationFrame(() => {
      const roll = rollRef.current;
      if (!roll) return;
      roll.scrollLeft = Math.max(0, (start / duration) * fitWidth * target - 24);
      syncRollView();
    });
  }

  /** Pointer position over the overview track as a 0–1 clip ratio. */
  function overviewRatio(clientX: number) {
    const track = overviewRef.current;
    if (!track) return 0;
    const rect = track.getBoundingClientRect();
    if (rect.width <= 0) return 0;
    return Math.min(1, Math.max(0, (clientX - rect.left) / rect.width));
  }

  /**
   * Grab the window where the pointer lands and drag it; a click outside the window
   * pulls that part of the clip into the middle of the roll.
   */
  function beginOverviewDrag(event: React.PointerEvent<HTMLDivElement>) {
    if (event.button !== 0) return;
    // Focus explicitly: preventDefault keeps the pointer from doing it for us.
    event.preventDefault();
    event.currentTarget.focus();
    const pointer = overviewRatio(event.clientX);
    const view = visibleGridWidth();
    const scroll = currentScrollLeft();
    const left = width > 0 ? scroll / width : 0;
    const right = width > 0 ? (scroll + view) / width : 1;
    overviewGrab.current = pointer >= left && pointer <= right ? pointer - (left + right) / 2 : 0;
    setOverviewDrag(true);
    scrollToRatio(pointer - overviewGrab.current);
  }

  useEffect(() => {
    if (!overviewDrag) return;
    const onMove = (event: PointerEvent) => {
      scrollToRatio(overviewRatio(event.clientX) - overviewGrab.current);
    };
    const onUp = () => setOverviewDrag(false);
    window.addEventListener("pointermove", onMove);
    window.addEventListener("pointerup", onUp);
    window.addEventListener("pointercancel", onUp);
    return () => {
      window.removeEventListener("pointermove", onMove);
      window.removeEventListener("pointerup", onUp);
      window.removeEventListener("pointercancel", onUp);
    };
  }, [overviewDrag, width]);

  /**
   * The overview is a slider over the scroll position: ←/→ pan a quarter of the
   * viewport, PageUp/PageDown a full viewport (slider order), Home/End jump, and
   * =/- zoom. The keys stop here so they never move the selected notes.
   */
  function handleOverviewKeys(event: React.KeyboardEvent<HTMLDivElement>) {
    if (event.metaKey || event.ctrlKey || event.altKey) return;
    const view = Math.max(1, visibleGridWidth());
    const scroll = currentScrollLeft();
    const run = (action: () => void) => {
      event.preventDefault();
      event.stopPropagation();
      action();
    };
    switch (event.key) {
      case "ArrowLeft":
        run(() => scrollToGrid(scroll - view * 0.25));
        return;
      case "ArrowRight":
        run(() => scrollToGrid(scroll + view * 0.25));
        return;
      case "PageUp":
        run(() => scrollToGrid(scroll + view));
        return;
      case "PageDown":
        run(() => scrollToGrid(scroll - view));
        return;
      case "Home":
        run(() => scrollToGrid(0));
        return;
      case "End":
        run(() => scrollToGrid(width));
        return;
      case "=":
      case "+":
        run(() => zoomBy(ZOOM_STEP));
        return;
      case "-":
      case "_":
        run(() => zoomBy(1 / ZOOM_STEP));
        return;
      default:
    }
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

  // Overview geometry. Before the roll is measured, show the whole clip rather than a
  // zero-width window; once measured, the window is the true visible slice of the grid.
  const barCount = Math.max(1, duration / secondsPerBar);
  const measured = rollView.clientWidth > 0;
  const visibleWidth = measured
    ? Math.max(0, Math.min(width, rollView.clientWidth - MIDI_GUTTER))
    : width;
  const maxScroll = Math.max(0, width - visibleWidth);
  const scrollRatio = maxScroll > 0 ? Math.min(1, Math.max(0, rollView.scrollLeft / maxScroll)) : 0;
  const overviewWindowPct = Math.min(100, Math.max(2, (visibleWidth / width) * 100));
  const overviewLeftPct = Math.min(
    100 - overviewWindowPct,
    Math.max(0, (rollView.scrollLeft / width) * 100)
  );
  const overviewBarStart = Math.min(
    barCount,
    1 + (width > 0 ? (rollView.scrollLeft / width) * barCount : 0)
  );
  const overviewBarEnd = Math.min(
    barCount,
    overviewBarStart + (width > 0 ? (visibleWidth / width) * barCount : 0)
  );
  const overviewTicks = Math.min(64, Math.max(1, Math.round(barCount)));

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

      <div className={`se-midi-overview${overviewDrag ? " is-dragging" : ""}`}>
        <div className="se-midi-overview-zoom">
          <button
            type="button"
            className="se-icon"
            aria-label="Zoom out the piano roll"
            title="Zoom out (Ctrl -)"
            disabled={zoom <= ZOOM_MIN}
            onClick={() => zoomBy(1 / ZOOM_STEP)}
          >
            <Icon name="fa-magnifying-glass-minus" />
          </button>
          <button
            type="button"
            className="se-icon"
            aria-label="Zoom in the piano roll"
            title="Zoom in (Ctrl =)"
            disabled={zoom >= ZOOM_MAX}
            onClick={() => zoomBy(ZOOM_STEP)}
          >
            <Icon name="fa-magnifying-glass-plus" />
          </button>
        </div>
        <div
          ref={overviewRef}
          className="se-midi-overview-track"
          role="slider"
          tabIndex={0}
          aria-label="Clip overview"
          aria-orientation="horizontal"
          aria-valuemin={0}
          aria-valuemax={100}
          aria-valuenow={Math.round(scrollRatio * 100)}
          aria-valuetext={`Bars ${overviewBarStart.toFixed(1)}–${overviewBarEnd.toFixed(
            1
          )} of ${barCount.toFixed(1)}`}
          title="Drag to scroll the piano roll; double-click to zoom here"
          onPointerDown={beginOverviewDrag}
          onDoubleClick={(event) => applyZoom(zoom * ZOOM_STEP, overviewRatio(event.clientX))}
          onKeyDown={handleOverviewKeys}
        >
          {Array.from({ length: Math.max(0, overviewTicks - 1) }).map((_, index) => (
            <span
              key={`overview-tick-${index}`}
              className="se-midi-overview-tick"
              style={{ left: `${((index + 1) / overviewTicks) * 100}%` }}
              aria-hidden="true"
            />
          ))}
          <span className="se-midi-overview-notes" aria-hidden="true">
            {shown.map((note) => (
              <span
                key={note.id}
                className="se-midi-overview-note"
                data-pitch={note.pitch}
                style={{
                  left: `${(note.start / duration) * 100}%`,
                  width: `${Math.max(0.6, (note.length / duration) * 100)}%`,
                  top: `${((MIDI_MAX_PITCH - note.pitch) / MIDI_PITCHES) * 100}%`,
                  background: clip.color || "hsl(var(--accent))",
                }}
              />
            ))}
          </span>
          <span
            className="se-midi-overview-window"
            aria-hidden="true"
            style={{ left: `${overviewLeftPct}%`, width: `${overviewWindowPct}%` }}
          />
        </div>
      </div>

      <div className="se-midi-roll" ref={rollRef} onScroll={syncRollView}>
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
            const seconds =
              ((event.clientX - rect.left - MIDI_GUTTER + currentScrollLeft()) / width) * duration;
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
            Math.max(
              0,
              ((event.clientX - rect.left - MIDI_GUTTER + currentScrollLeft()) / width) * duration
            )
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
          <span className="se-midi-velocity-baseline" aria-hidden="true" />
        ) : null}
        {/* The lanes share the note grid's x-axis, so they follow its scroll. */}
        <div
          className="se-midi-lane-scroll"
          style={{ transform: `translateX(${-rollView.scrollLeft}px)` }}
        >
          {lane === "velocity" ? (
            shown.map((note) => {
              const height = Math.max(2, (note.velocity / 127) * 52);
              return (
                <span key={note.id}>
                  <span
                    className={`se-midi-velocity-bar${
                      velocityDrag?.id === note.id ? " is-active" : ""
                    }`}
                    style={{ left: MIDI_GUTTER + (note.start / duration) * width, height }}
                  />
                  <span
                    className={`se-midi-velocity-dot${
                      velocityDrag?.id === note.id ? " is-active" : ""
                    }`}
                    style={{
                      left: MIDI_GUTTER + (note.start / duration) * width + 1,
                      bottom: 8 + height,
                    }}
                  />
                </span>
              );
            })
          ) : (
            <svg
              className="se-midi-lane-svg"
              viewBox={`0 0 ${MIDI_GUTTER + width} 64`}
              style={{ width: MIDI_GUTTER + width }}
              preserveAspectRatio="none"
              aria-hidden="true"
            >
              <line
                x1={MIDI_GUTTER}
                x2={MIDI_GUTTER + width}
                y1={lane === "bend" ? 32 : 60}
                y2={lane === "bend" ? 32 : 60}
                className="se-midi-lane-base"
              />
              {(() => {
                const points =
                  lane === "bend"
                    ? sanitizePoints(clip.midi?.bend, -1, 1)
                    : sanitizePoints(clip.midi?.mod, 0, 1);
                const px = (point: { at: number }) =>
                  MIDI_GUTTER + (point.at / duration) * width;
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
