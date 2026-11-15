/**
 * Time-selection editing (N-01).
 *
 * The reference has a second selection type beside the clip selection: a time range
 * dragged on the bar ruler. That range owns its own verbs — delete time, duplicate
 * time, loop the selection and export it — and the edits ripple the arrangement
 * rather than deleting whole clips (spec §16, §36, §87).
 *
 * Kept pure so the arithmetic is testable without a browser: the shell owns the
 * pointer session and the document write, this module only reshapes clips.
 */

import type { MidiNote } from "@/lib/studio-midi";

/** A half-open time range in seconds: `start` inclusive, `end` exclusive. */
export type TimeRange = { start: number; end: number };

/** The slice of a lane clip this module touches; everything else is carried through. */
export type TimeClip = {
  id: string;
  start?: number;
  duration?: number;
  offset?: number;
  fadeIn?: number;
  fadeOut?: number;
  midi?: { notes?: MidiNote[]; [key: string]: unknown };
  [key: string]: unknown;
};

export type TimeTrack = { id: string; clipIds: string[] };

export type TimeEdit = { lanes: TimeClip[]; tracks: TimeTrack[] };

/** Sub-sample tolerance; anything smaller is rounding noise from the grid. */
export const TIME_EPSILON = 0.0001;

function round(value: number): number {
  return Number(value.toFixed(6));
}

function clipSpan(clip: TimeClip) {
  const start = typeof clip.start === "number" ? clip.start : 0;
  const duration =
    typeof clip.duration === "number" && clip.duration > 0 ? clip.duration : 4;
  return {
    start,
    duration,
    end: start + duration,
    offset: typeof clip.offset === "number" ? clip.offset : 0,
  };
}

/** Order two drag positions into a range, dropping empty selections. */
export function normaliseRange(a: number, b: number): TimeRange | null {
  const start = Math.max(0, Math.min(a, b));
  const end = Math.max(0, Math.max(a, b));
  return end - start > TIME_EPSILON ? { start: round(start), end: round(end) } : null;
}

export function rangeLength(range: TimeRange): number {
  return Math.max(0, range.end - range.start);
}

/**
 * The slice of a clip between two absolute times, re-based to `start`.
 *
 * The content offset moves with the slice so audio keeps its musical place, and MIDI
 * notes are rebased, clipped to the slice and dropped when they fall outside it.
 */
function part(
  clip: TimeClip,
  from: number,
  to: number,
  start: number,
  id: string
): TimeClip {
  const span = clipSpan(clip);
  const duration = Math.max(0, to - from);
  const next: TimeClip = {
    ...clip,
    id,
    start: round(start),
    duration: round(duration),
    offset: round(span.offset + (from - span.start)),
  };
  if (typeof clip.fadeIn === "number") {
    next.fadeIn = round(Math.min(clip.fadeIn, duration));
  }
  if (typeof clip.fadeOut === "number") {
    next.fadeOut = round(Math.min(clip.fadeOut, duration));
  }
  if (clip.midi) {
    next.midi = sliceMidi(clip.midi, from - span.start, duration);
  }
  return next;
}

function sliceMidi(
  midi: NonNullable<TimeClip["midi"]>,
  from: number,
  length: number
): NonNullable<TimeClip["midi"]> {
  if (!midi.notes?.length) return midi;
  const notes: MidiNote[] = [];
  for (const note of midi.notes) {
    const noteStart = note.start - from;
    const noteEnd = noteStart + note.length;
    const start = Math.max(0, noteStart);
    const end = Math.min(length, noteEnd);
    if (end - start <= TIME_EPSILON) continue;
    notes.push({ ...note, start: round(start), length: round(end - start) });
  }
  return { ...midi, notes };
}

function uniqueId(base: string, taken: Set<string>): string {
  let id = base;
  let index = 2;
  while (taken.has(id)) id = `${base}-${index++}`;
  taken.add(id);
  return id;
}

/**
 * Split one clip at the given absolute times.
 *
 * The first segment keeps the clip's id so selection and history stay put; later
 * segments get `<id>-split-2`, `-3`… Cuts at or outside the clip's own bounds are
 * ignored, so callers can pass raw transient times.
 */
export function splitClipAtTimes<T extends TimeClip>(clip: T, times: number[]): T[] {
  const span = clipSpan(clip);
  const cuts = Array.from(new Set(times.map(round)))
    .filter((time) => time > span.start + TIME_EPSILON && time < span.end - TIME_EPSILON)
    .sort((a, b) => a - b);
  if (cuts.length === 0) return [clip];
  const bounds = [span.start, ...cuts, span.end];
  const taken = new Set([clip.id]);
  const segments: T[] = [];
  for (let index = 0; index < bounds.length - 1; index += 1) {
    const from = bounds[index];
    const to = bounds[index + 1];
    const id = index === 0 ? clip.id : uniqueId(`${clip.id}-split`, taken);
    segments.push(part(clip, from, to, from, id) as T);
  }
  // A hard cut only keeps the outer fades: in on the head, out on the tail.
  segments.forEach((segment, index) => {
    if (index > 0) delete segment.fadeIn;
    if (index < segments.length - 1) delete segment.fadeOut;
  });
  return segments;
}

/** Rebuild each track's clip list in lane order, including the ids the edit created. */
function rebuildTracks<T extends TimeTrack>(
  tracks: T[],
  lanes: TimeClip[],
  owner: Map<string, string>
): T[] {
  return tracks.map(
    (track) =>
      ({
        ...track,
        clipIds: lanes
          .filter((clip) => owner.get(clip.id) === track.id)
          .map((clip) => clip.id),
      }) as T
  );
}

/** True when the clip belongs to a track the edit is allowed to touch. */
function inScope(trackId: string | undefined, scope: Set<string> | null): boolean {
  if (!scope) return true;
  return trackId !== undefined && scope.has(trackId);
}

/**
 * Delete a block of time and ripple everything after it left.
 *
 * - clips fully inside the range disappear;
 * - a clip the range cuts keeps its left head and/or right tail, with the tail moved
 *   up to the start of the gap and its content offset advanced past the deleted audio;
 * - later clips on the same tracks slide left by the range length.
 *
 * `trackIds` limits the edit to those tracks (the reference's "Delete Time on Selected
 * Tracks"); omit it to edit every track ("Delete Time").
 */
export function deleteTimeRange<T extends TimeTrack>(
  edit: { lanes: TimeClip[]; tracks: T[] },
  range: TimeRange,
  trackIds?: string[]
): { lanes: TimeClip[]; tracks: T[] } {
  const length = rangeLength(range);
  if (length <= TIME_EPSILON) return edit;
  const scope = trackIds && trackIds.length ? new Set(trackIds) : null;
  const owner = new Map<string, string>();
  for (const track of edit.tracks) {
    for (const id of track.clipIds) owner.set(id, track.id);
  }
  const taken = new Set(edit.lanes.map((clip) => clip.id));

  const lanes: TimeClip[] = [];
  for (const clip of edit.lanes) {
    const trackId = owner.get(clip.id);
    const span = clipSpan(clip);

    if (!inScope(trackId, scope) || span.end <= range.start + TIME_EPSILON) {
      lanes.push(clip);
      continue;
    }
    if (span.start >= range.end - TIME_EPSILON) {
      lanes.push({ ...clip, start: round(span.start - length) });
      continue;
    }

    const hasHead = span.start < range.start - TIME_EPSILON;
    if (hasHead) {
      const head = part(clip, span.start, range.start, span.start, clip.id);
      lanes.push(head);
      if (trackId) owner.set(head.id, trackId);
    }
    if (span.end > range.end + TIME_EPSILON) {
      // A clip with no head keeps its id, so keyboard focus and the DOM selection
      // survive the edit; only a second piece needs a new id.
      const tail = part(
        clip,
        range.end,
        span.end,
        range.start,
        hasHead ? uniqueId(`${clip.id}~r`, taken) : clip.id
      );
      lanes.push(tail);
      if (trackId) owner.set(tail.id, trackId);
    }
  }

  return { lanes, tracks: rebuildTracks(edit.tracks, lanes, owner) };
}

/**
 * Copy the content of a range and insert it immediately after the range, pushing the
 * rest of each affected track right. Cuts clips at both range edges; MIDI notes travel
 * with their slice.
 *
 * `trackIds` limits the edit to those tracks, like {@link deleteTimeRange}.
 */
export function duplicateTimeRange<T extends TimeTrack>(
  edit: { lanes: TimeClip[]; tracks: T[] },
  range: TimeRange,
  trackIds?: string[]
): { lanes: TimeClip[]; tracks: T[] } {
  const length = rangeLength(range);
  if (length <= TIME_EPSILON) return edit;
  const scope = trackIds && trackIds.length ? new Set(trackIds) : null;
  const owner = new Map<string, string>();
  for (const track of edit.tracks) {
    for (const id of track.clipIds) owner.set(id, track.id);
  }
  const taken = new Set(edit.lanes.map((clip) => clip.id));

  const lanes: TimeClip[] = [];
  for (const clip of edit.lanes) {
    const trackId = owner.get(clip.id);
    const span = clipSpan(clip);

    if (!inScope(trackId, scope) || span.end <= range.start + TIME_EPSILON) {
      lanes.push(clip);
      continue;
    }
    if (span.start >= range.end - TIME_EPSILON) {
      lanes.push({ ...clip, start: round(span.start + length) });
      continue;
    }

    const from = Math.max(span.start, range.start);
    const to = Math.min(span.end, range.end);

    if (span.start < from - TIME_EPSILON) {
      const head = part(clip, span.start, from, span.start, clip.id);
      lanes.push(head);
      if (trackId) owner.set(head.id, trackId);
    }
    // The copy lands where the range ends; the original stays where it was.
    const copy = part(clip, from, to, from + length, uniqueId(`${clip.id}~d`, taken));
    lanes.push(copy);
    if (trackId) owner.set(copy.id, trackId);

    const mid = part(
      clip,
      from,
      to,
      from,
      span.start < from - TIME_EPSILON ? uniqueId(`${clip.id}~m`, taken) : clip.id
    );
    lanes.push(mid);
    if (trackId) owner.set(mid.id, trackId);

    if (span.end > to + TIME_EPSILON) {
      const tail = part(
        clip,
        to,
        span.end,
        to + length,
        uniqueId(`${clip.id}~r`, taken)
      );
      lanes.push(tail);
      if (trackId) owner.set(tail.id, trackId);
    }
  }

  return { lanes, tracks: rebuildTracks(edit.tracks, lanes, owner) };
}
