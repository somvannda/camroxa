/**
 * Warp markers and stretch modes (S30).
 *
 * The reference stores markers per clip as a map of *source position (beats)* to
 * *timeline time (seconds)*; the three Stretch modes differ only in which positions are
 * auto-generated (`On Beat`, `Transients`, `Start and End`). This module keeps the same
 * shape in a more explicit form — one entry per marker with both positions — because
 * every consumer (rendering, dragging, quantizing) needs the pair, not the map.
 *
 * Pure: the caller decodes audio and owns the document write.
 */

import { detectOnsets } from "@/lib/studio-peaks";
import { snapToGrid } from "@/lib/studio-snap";

export type WarpMode = "beat" | "transients" | "start-end";

export type WarpMarker = {
  id: string;
  /** Timeline position in seconds, relative to the clip start. */
  time: number;
  /** Source position in seconds, relative to the audio file. */
  source: number;
};

export type WarpState = {
  /** Stretch switch; markers only render while it is on (captured S30). */
  on: boolean;
  mode: WarpMode;
  /** 0–100 %, the captured "Formant" control. */
  formant: number;
  markers: WarpMarker[];
};

/** Copy and tooltips are the captured ones (spec §94). */
export const WARP_MODES: Array<{ value: WarpMode; label: string; hint: string }> = [
  {
    value: "beat",
    label: "On Beat",
    hint: "Minimal markers to account for tempo changes, placed on musical beats.",
  },
  {
    value: "transients",
    label: "Transients",
    hint: "Markers placed on transients and note starts.",
  },
  {
    value: "start-end",
    label: "Start and End",
    hint: "Minimal markers that maintain average BPM and first-beat-offset of the full song.",
  },
];

export const DEFAULT_WARP: WarpState = {
  on: false,
  mode: "transients",
  formant: 0,
  markers: [],
};

/** A dense transient pass is ~358 markers in the capture; this keeps a document sane. */
export const WARP_MARKER_LIMIT = 600;

function round(value: number): number {
  return Number(value.toFixed(6));
}

function finite(value: unknown, fallback: number): number {
  return typeof value === "number" && Number.isFinite(value) ? value : fallback;
}

/** Whatever the document holds, coerced into a state the editor can trust. */
export function sanitizeWarp(value: unknown): WarpState {
  if (!value || typeof value !== "object") return DEFAULT_WARP;
  const source = value as Record<string, unknown>;
  const mode = WARP_MODES.some((entry) => entry.value === source.mode)
    ? (source.mode as WarpMode)
    : DEFAULT_WARP.mode;
  const rawMarkers = Array.isArray(source.markers) ? source.markers : [];
  const markers: WarpMarker[] = [];
  rawMarkers.slice(0, WARP_MARKER_LIMIT).forEach((entry, index) => {
    if (!entry || typeof entry !== "object") return;
    const marker = entry as Record<string, unknown>;
    const time = finite(marker.time, Number.NaN);
    if (!Number.isFinite(time)) return;
    markers.push({
      id: typeof marker.id === "string" && marker.id ? marker.id : `m${index}`,
      time: Math.max(0, round(time)),
      source: Math.max(0, round(finite(marker.source, time))),
    });
  });
  markers.sort((a, b) => a.time - b.time);
  return {
    on: Boolean(source.on),
    mode,
    formant: Math.max(0, Math.min(100, finite(source.formant, 0))),
    markers,
  };
}

export type GenerateOptions = {
  mode: WarpMode;
  /** Clip length in seconds. */
  duration: number;
  secondsPerBar: number;
  beatsPerBar: number;
  /** Source offset of the clip, so `source` keeps pointing into the file. */
  offset?: number;
  /** Decoded peak envelope; absent falls back to a grid. */
  peaks?: number[] | null;
};

/**
 * Auto-place markers for a stretch mode. `Transients` needs decoded peaks: without
 * them it falls back to `Start and End` rather than inventing analysis it did not do.
 */
export function generateWarpMarkers({
  mode,
  duration,
  secondsPerBar,
  beatsPerBar,
  offset = 0,
  peaks = null,
}: GenerateOptions): WarpMarker[] {
  const length = Math.max(0, duration);
  const marker = (time: number, index: number): WarpMarker => ({
    id: `${mode}-${index}`,
    time: round(Math.max(0, Math.min(length, time))),
    source: round(Math.max(0, offset + Math.min(length, time))),
  });

  if (mode === "start-end") {
    return length > 0 ? [marker(0, 0), marker(length, 1)] : [];
  }

  if (mode === "transients") {
    const onsets = detectOnsets(peaks);
    // A single onset (the clip start) means the envelope had nothing to analyse, e.g. a
    // steady tone: keep the honest bounds fallback instead of one lone marker.
    if (onsets.length < 2) return generateWarpMarkers({
      mode: "start-end",
      duration,
      secondsPerBar,
      beatsPerBar,
      offset,
    });
    const seen = new Set<number>();
    const markers: WarpMarker[] = [];
    for (const fraction of onsets) {
      const time = round(fraction * length);
      if (seen.has(time)) continue;
      seen.add(time);
      markers.push(marker(time, markers.length));
      if (markers.length >= WARP_MARKER_LIMIT) break;
    }
    return markers;
  }

  const step = secondsPerBar / Math.max(1, beatsPerBar);
  if (length <= 0 || step <= 0) return [];
  const markers: WarpMarker[] = [];
  for (let time = 0; time <= length + 0.0001; time += step) {
    markers.push(marker(time, markers.length));
    if (markers.length >= WARP_MARKER_LIMIT) break;
  }
  return markers;
}

/** Snap every marker's timeline position to the grid; ties collapse to one marker. */
export function quantiseWarpMarkers(
  markers: WarpMarker[],
  secondsPerBar: number,
  beatsPerBar: number
): WarpMarker[] {
  const seen = new Set<number>();
  const next: WarpMarker[] = [];
  for (const marker of markers) {
    const time = round(snapToGrid(marker.time, secondsPerBar, beatsPerBar));
    const key = Math.round(time * 1000);
    if (seen.has(key)) continue;
    seen.add(key);
    next.push({ ...marker, time });
  }
  return next.sort((a, b) => a.time - b.time);
}

/** Move one marker (dragging its head), keeping the pair sorted by time. */
export function moveWarpMarker(
  markers: WarpMarker[],
  id: string,
  time: number,
  duration: number
): WarpMarker[] {
  const clamped = round(Math.max(0, Math.min(duration, time)));
  return markers
    .map((marker) => (marker.id === id ? { ...marker, time: clamped } : marker))
    .sort((a, b) => a.time - b.time);
}
