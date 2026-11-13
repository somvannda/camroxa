import { createHash, randomUUID } from "node:crypto";

/**
 * Suno Studio document codec.
 *
 * Converts the platform project document (seconds, 0–100 mixer values, flat
 * `lanes` list) into Suno's Studio `state` (beats, 0–1 amplitudes, per-track
 * `clips`) and back.
 *
 * The schema is derived from real documents captured on 2026-11-13
 * (`docs/studio/SUNO_STUDIO_STATE_SCHEMA.md`), not guessed:
 *
 *   state = {
 *     timing: { type: "manual"|"follow-track", bps, bpsAutomation, lockBPS?, fallbackBPS?, trackId? },
 *     timeSignatureChanges: [{ startBeats, subdivisionsPerBar, beatsPerSubdivision }],
 *     amplitude, songFadeInBeats, songFadeOutBeats,
 *     loop: { enabled, startBeats, endBeats },
 *     metronome: { enabled, amplitude },
 *     editorPointerModes: { midi, audio },
 *     tracks: [{
 *       id, name, color, type: "audio"|"midi", height, mute, solo, arm, hidden,
 *       amplitude, balance, routingMode, signalChain, eq, faderAutomation,
 *       clips: [{
 *         id, type, name, color?, startBeats, endBeats, readStartBeats,
 *         fadeInBeats, fadeOutBeats, fadeInCurve, fadeOutCurve, mute,
 *         loop: { enabled, startBeats, endBeats },
 *         midi?: { notes: [{ id: number, startBeats, durationBeats, pitch, velocity }],
 *                  controlChanges, pitchBend, channelPressure, sysex },
 *         asset?: { id, type },
 *       }],
 *       takeLanes, takeLanesExpanded, clipCreationIntents,
 *     }],
 *   }
 *
 * Fields we do not generate are preserved from the baseline document, so a Suno
 * key we have not modelled yet survives a save.
 */

export interface LocalMidiNote {
  id?: string;
  pitch: number;
  start: number;
  length: number;
  velocity: number;
}

export interface LocalClip {
  id: string;
  title?: string;
  color?: string;
  start?: number;
  duration?: number;
  songId?: string | null;
  sunoId?: string | null;
  sunoAssetId?: string | null;
  midi?: { notes?: LocalMidiNote[] };
  [key: string]: unknown;
}

export interface LocalTrack {
  id: string;
  name?: string;
  color?: string;
  volume?: number;
  pan?: number;
  muted?: boolean;
  solo?: boolean;
  hidden?: boolean;
  index?: number;
  clipIds?: string[];
  volumeAutomation?: Array<{ time: number; value: number }>;
  panAutomation?: Array<{ time: number; value: number }>;
  sunoId?: string | null;
  chain?: unknown[];
  [key: string]: unknown;
}

export interface LocalDocument {
  tracks?: LocalTrack[];
  lanes?: LocalClip[];
  /** Ruler section markers: seconds + label, as the editor stores them. */
  markers?: Array<{ id: string; time: number; label?: string; color?: string }>;
  masterVolume?: number;
  masterMuted?: boolean;
  loopStart?: number;
  loopEnd?: number;
  [key: string]: unknown;
}

export interface CodecInput {
  title: string;
  majorVersion: number;
  bpm: number;
  timeSignature: string;
  data: LocalDocument;
  /** Last document Suno returned; unknown keys are preserved. */
  baseline?: Record<string, unknown> | null;
}

export interface CodecResult {
  state: Record<string, unknown>;
  /** Local clip ids that cannot be represented on Suno yet (no Suno asset). */
  skippedClipIds: string[];
}

/** Round a float to 6 decimals so a save does not churn on float noise. */
function round(value: number): number {
  return Number.isFinite(value) ? Math.round(value * 1e6) / 1e6 : 0;
}

export function beatsFromSeconds(seconds: number, bps: number): number {
  return round((Number(seconds) || 0) * bps);
}

export function secondsFromBeats(beats: number, bps: number): number {
  return bps > 0 ? round((Number(beats) || 0) / bps) : 0;
}

/**
 * Deterministic UUID-shaped id for a local id. Suno's ids are UUIDs and we need
 * the same track/clip to keep its identity across saves and pulls.
 */
export function stableSunoId(localId: string): string {
  const hex = createHash("sha256").update(`camxora:${localId}`).digest("hex");
  return `${hex.slice(0, 8)}-${hex.slice(8, 12)}-5${hex.slice(13, 16)}-a${hex.slice(17, 20)}-${hex.slice(20, 32)}`;
}

/** `4/4` → Suno's `{subdivisionsPerBar, beatsPerSubdivision}`. */
export function timeSignatureParts(signature: string): {
  subdivisionsPerBar: number;
  beatsPerSubdivision: number;
} {
  const match = /^(\d{1,2})\s*\/\s*(\d{1,2})$/.exec(String(signature ?? "").trim());
  const numerator = match ? Math.max(1, Math.min(32, Number(match[1]))) : 4;
  const denominator = match ? Math.max(1, Math.min(32, Number(match[2]))) : 4;
  return {
    subdivisionsPerBar: numerator,
    beatsPerSubdivision: round(4 / denominator),
  };
}

export function timeSignatureFromState(
  changes: unknown
): string {
  const first = Array.isArray(changes) ? (changes[0] as Record<string, unknown> | undefined) : undefined;
  if (!first) return "4/4";
  const numerator = Number(first.subdivisionsPerBar) || 4;
  const perSubdivision = Number(first.beatsPerSubdivision) || 1;
  const denominator = Math.round(4 / perSubdivision) || 4;
  return `${numerator}/${denominator}`;
}

/** BPM from a Suno timing block (`bps` is beats per second). */
export function bpmFromState(timing: unknown): number {
  const block = (timing ?? {}) as Record<string, unknown>;
  const bps = Number(block.bps ?? block.fallbackBPS);
  if (!Number.isFinite(bps) || bps <= 0) return 120;
  return Math.round(bps * 60);
}

/** Suno's note id is numeric; derive a stable positive int32 from ours. */
export function noteId(value: string | undefined, fallbackIndex: number): number {
  const source = value ?? `note-${fallbackIndex}`;
  const hash = createHash("sha256").update(source).digest();
  const n = hash.readUInt32BE(0) & 0x7fffffff;
  return n === 0 ? fallbackIndex + 1 : n;
}

function midiFromLocal(
  clip: LocalClip,
  bps: number
): Record<string, unknown> | null {
  if (!clip.midi) return null;
  const notes = Array.isArray(clip.midi.notes) ? clip.midi.notes : [];
  return {
    notes: notes.map((note, index) => ({
      id: noteId(note.id, index),
      startBeats: beatsFromSeconds(note.start, bps),
      durationBeats: Math.max(0.01, beatsFromSeconds(note.length, bps)),
      pitch: Math.max(0, Math.min(127, Math.round(Number(note.pitch) || 0))),
      velocity: Math.max(1, Math.min(127, Math.round(Number(note.velocity) || 100))),
    })),
    controlChanges: [],
    pitchBend: [],
    channelPressure: [],
    sysex: [],
  };
}

function localClipsForTrack(data: LocalDocument, track: LocalTrack): LocalClip[] {
  const lanes = Array.isArray(data.lanes) ? data.lanes : [];
  const ids = new Set(track.clipIds ?? []);
  const byId = lanes.filter((clip) => ids.has(clip.id));
  if (byId.length > 0) return byId;
  // Fallback for documents written before tracks carried clipIds.
  return lanes.filter((clip) => (clip as { trackId?: string }).trackId === track.id);
}

function sunoClipFromLocal(
  clip: LocalClip,
  track: LocalTrack,
  bps: number
): { clip: Record<string, unknown> } | { skip: string } {
  const start = Number(clip.start) || 0;
  const duration = Math.max(0, Number(clip.duration) || 0);
  const startBeats = beatsFromSeconds(start, bps);
  const endBeats = beatsFromSeconds(start + duration, bps);
  const readStartBeats = beatsFromSeconds(Number(clip.offset) || 0, bps);
  const fadeInBeats = Math.max(0, beatsFromSeconds(Number(clip.fadeIn) || 0, bps));
  const midi = midiFromLocal(clip, bps);
  const assetId =
    typeof clip.sunoAssetId === "string" && clip.sunoAssetId ? clip.sunoAssetId : null;
  if (!midi && !assetId) return { skip: clip.id };

  const body: Record<string, unknown> = {
    id: clip.sunoId ?? stableSunoId(clip.id),
    type: midi ? "midi" : "audio",
    name: clip.title ?? "Clip",
    color: clip.color ?? track.color,
    startBeats,
    endBeats,
    readStartBeats,
    fadeInBeats,
    fadeOutBeats: 0,
    fadeInCurve: 1,
    fadeOutCurve: 1,
    mute: false,
    loop: { enabled: false, startBeats: readStartBeats, endBeats },
  };
  if (midi) body.midi = midi;
  if (assetId) {
    // Audio clips reference a Suno-owned clip asset. `type` is always "clip" in
    // every captured project; `clipId` is the source clip, not the timeline id.
    body.asset = { id: assetId, type: "clip" };
    body.clipId = assetId;
    body.amplitude = 1;
    body.transposition = 0;
    body.streaming = false;
    body.reversed = false;
    body.formantCorrection = 0;
    body.warp = { enabled: false, markersHash: "", awaitingAnalysis: false };
  }
  return { clip: body };
}

function automationToBeats(
  points: unknown,
  bps: number
): Array<{ timeBeats: number; value: number }> {
  if (!Array.isArray(points)) return [];
  return points
    .map((point) => {
      const record = (point ?? {}) as Record<string, unknown>;
      return {
        timeBeats: beatsFromSeconds(Number(record.time) || 0, bps),
        value: round(Number(record.value) || 0),
      };
    })
    .sort((a, b) => a.timeBeats - b.timeBeats);
}

/** Sections are a registry keyed by id: {id, name, startBeats, endBeats, color}. */
function sectionsFromMarkers(
  markers: LocalDocument["markers"],
  bps: number,
  contentEndBeats: number
): Record<string, unknown> {
  const list = (Array.isArray(markers) ? markers : [])
    .map((marker) => ({
      id: String(marker.id),
      beats: beatsFromSeconds(Number(marker.time) || 0, bps),
      name: String(marker.label ?? "Section").slice(0, 80) || "Section",
      color: typeof marker.color === "string" ? marker.color : "#7c5cff",
    }))
    .sort((a, b) => a.beats - b.beats);
  const sections: Record<string, unknown> = {};
  list.forEach((marker, index) => {
    const next = list[index + 1];
    const endBeats = next
      ? next.beats
      : Math.max(marker.beats + 1, contentEndBeats);
    sections[marker.id] = {
      id: marker.id,
      name: marker.name,
      startBeats: marker.beats,
      endBeats,
      color: marker.color,
    };
  });
  return sections;
}

function markersFromState(
  sections: unknown,
  bps: number
): Array<{ id: string; time: number; label: string; color?: string }> {
  if (!sections || typeof sections !== "object" || Array.isArray(sections)) return [];
  return Object.entries(sections as Record<string, Record<string, unknown>>)
    .map(([key, section]) => ({
      id: String(section?.id ?? key),
      time: secondsFromBeats(Number(section?.startBeats) || 0, bps),
      label: String(section?.name ?? "Section"),
      color: typeof section?.color === "string" ? section.color : undefined,
    }))
    .sort((a, b) => a.time - b.time);
}

/**
 * Build the Suno document for one Camxora project.
 *
 * The arrangement is generated from the local document (local-first mirror).
 * Every top-level key we do not generate — selection, layout, panel state,
 * warp registries, plugin instances we do not model — is copied from the
 * baseline so a save never erases Suno state we have not mapped yet.
 */
export function projectDocumentToSunoState(input: CodecInput): CodecResult {
  const bpm = Math.max(20, Math.min(300, Number(input.bpm) || 120));
  const bps = round(bpm / 60);
  const data = input.data ?? {};
  const tracks = Array.isArray(data.tracks) ? data.tracks : [];
  const signature = timeSignatureParts(input.timeSignature);
  const skippedClipIds: string[] = [];

  const sunoTracks = tracks
    .slice()
    .sort((a, b) => (Number(a.index) || 0) - (Number(b.index) || 0))
    .map((track) => {
      const trackId = track.sunoId ?? stableSunoId(track.id);
      const localClips = localClipsForTrack(data, track);
      const built = localClips
        .map((clip) => sunoClipFromLocal(clip, track, bps))
        .filter((entry): entry is { clip: Record<string, unknown> } => {
          if ("skip" in entry) {
            skippedClipIds.push(entry.skip);
            return false;
          }
          return true;
        })
        .map((entry) => entry.clip);
      const builtIds = new Set(built.map((clip) => clip.id));
      // Keep clips the baseline owns that we did not rebuild (audio we cannot
      // represent yet, or clips added on Suno). Dropping them would delete real
      // audio from the mirrored project.
      const baselineTrack = Array.isArray(input.baseline?.tracks)
        ? (input.baseline?.tracks as Array<Record<string, unknown>>).find(
            (candidate) => candidate.id === trackId
          )
        : undefined;
      const preserved = Array.isArray(baselineTrack?.clips)
        ? (baselineTrack?.clips as Array<Record<string, unknown>>).filter(
            (clip) => !builtIds.has(clip.id)
          )
        : [];
      const clips = [...built, ...preserved];
      const hasMidi = clips.some((clip) => clip.type === "midi");
      return {
        id: trackId,
        name: track.name ?? "Track",
        color: track.color ?? "#7c5cff",
        type: hasMidi ? "midi" : "audio",
        height: 88,
        mute: Boolean(track.muted),
        solo: Boolean(track.solo),
        arm: false,
        hidden: Boolean(track.hidden),
        amplitude: round(Math.max(0, Math.min(1.2, (Number(track.volume ?? 80) || 0) / 100))),
        balance: round(Math.max(-1, Math.min(1, (Number(track.pan ?? 0) || 0) / 100))),
        routingMode: "stereo",
        signalChain: [],
        faderAutomation: automationToBeats(track.volumeAutomation, bps),
        clips,
        takeLanes: [
          {
            id: stableSunoId(`${track.id}:take-lane`),
            name: "Take 1",
            type: hasMidi ? "midi" : "audio",
            height: 32,
            dismissed: true,
            clips: [],
            clipCreationIntents: [],
          },
        ],
        takeLanesExpanded: false,
        clipCreationIntents: [],
      };
    });

  const fallbackTracks = Array.isArray((input.baseline ?? {}).tracks)
    ? ((input.baseline ?? {}).tracks as unknown[])
    : null;
  const contentEndBeats = sunoTracks.reduce((max, track) => {
    for (const clip of track.clips as Array<Record<string, unknown>>) {
      const end = Number(clip.endBeats) || 0;
      if (end > max) max = end;
    }
    return max;
  }, 0);  // A local document with no tracks is ambiguous: it can mean "every track was
  // deleted" or "the data never loaded". Never wipe a Suno-only project on the
  // ambiguous case; a real delete still pushes when at least one track remains.
  const nextTracks = sunoTracks.length > 0 || fallbackTracks === null ? sunoTracks : fallbackTracks;

  const state: Record<string, unknown> = {
    ...(input.baseline ?? {}),
    title: String(input.title ?? "").trim().slice(0, 120) || "Untitled Project",
    majorVersion: Math.max(1, Math.min(10, Number(input.majorVersion) || 2)),
    timing: {
      type: "manual",
      bps,
      bpsAutomation: [],
      lockBPS: false,
    },
    timeSignatureChanges: [
      {
        startBeats: 0,
        subdivisionsPerBar: signature.subdivisionsPerBar,
        beatsPerSubdivision: signature.beatsPerSubdivision,
      },
    ],
    amplitude: round(Math.max(0, Math.min(1.2, (Number(data.masterVolume ?? 100) || 0) / 100))),
    songFadeInBeats: 0,
    songFadeOutBeats: 0,
    loop: {
      enabled: Number(data.loopEnd ?? 0) > Number(data.loopStart ?? 0),
      startBeats: beatsFromSeconds(Number(data.loopStart ?? 0) || 0, bps),
      endBeats: beatsFromSeconds(Number(data.loopEnd ?? 0) || 0, bps),
    },
    metronome: { enabled: false, amplitude: 1 },
    editorPointerModes: { midi: "select", audio: "select" },
    sections: sectionsFromMarkers(data.markers, bps, contentEndBeats),
    tracks: nextTracks,
    selection: {
      trackIds: nextTracks.map((track) => (track as { id?: string }).id ?? ""),
      focusedTrackId: (nextTracks[0] as { id?: string } | undefined)?.id ?? null,
      noteIds: [],
      anchorBeats: 0,
      focusBeats: 0,
      contextBeforeBeats: 32,
      contextAfterBeats: 32,
      focusedArea: "timeline",
      warpMarkerSeconds: {},
    },
  };

  return { state, skippedClipIds };
}

/**
 * Read a Suno document back into local project fields. Used by the pull path and
 * by the round-trip test; only fields with a verified mapping are projected.
 */
export function sunoStateToProjectData(state: Record<string, unknown>): {
  bpm: number;
  timeSignature: string;
  tracks: LocalTrack[];
  lanes: LocalClip[];
  markers: Array<{ id: string; time: number; label: string; color?: string }>;
} {
  const bpm = bpmFromState(state.timing);
  const bps = round(bpm / 60);
  const signature = timeSignatureFromState(state.timeSignatureChanges);
  const tracks: LocalTrack[] = [];
  const lanes: LocalClip[] = [];

  const sunoTracks = Array.isArray(state.tracks) ? state.tracks : [];
  sunoTracks.forEach((entry, index) => {
    const track = (entry ?? {}) as Record<string, unknown>;
    const trackId = typeof track.id === "string" ? track.id : `track-${index}`;
    const clips = Array.isArray(track.clips) ? track.clips : [];
    const clipIds: string[] = [];
    clips.forEach((raw, clipIndex) => {
      const clip = (raw ?? {}) as Record<string, unknown>;
      const clipId = typeof clip.id === "string" ? clip.id : `${trackId}-clip-${clipIndex}`;
      clipIds.push(clipId);
      const midi = clip.midi as { notes?: Array<Record<string, unknown>> } | undefined;
      lanes.push({
        id: clipId,
        sunoId: clipId,
        title: typeof clip.name === "string" ? clip.name : "Clip",
        color: typeof clip.color === "string" ? clip.color : undefined,
        start: secondsFromBeats(Number(clip.startBeats) || 0, bps),
        duration: secondsFromBeats(
          (Number(clip.endBeats) || 0) - (Number(clip.startBeats) || 0),
          bps
        ),
        offset: secondsFromBeats(Number(clip.readStartBeats) || 0, bps),
        fadeIn: secondsFromBeats(Number(clip.fadeInBeats) || 0, bps),
        midi: midi
          ? {
              notes: (midi.notes ?? []).map((note) => ({
                id: String(note.id ?? ""),
                pitch: Number(note.pitch) || 0,
                start: secondsFromBeats(Number(note.startBeats) || 0, bps),
                length: secondsFromBeats(Number(note.durationBeats) || 0, bps),
                velocity: Number(note.velocity) || 100,
              })),
            }
          : undefined,
        songId: (clip.asset as { id?: string } | undefined)?.id,
        sunoAssetId: (clip.asset as { id?: string } | undefined)?.id,
      });
    });
    tracks.push({
      id: trackId,
      sunoId: trackId,
      name: typeof track.name === "string" ? track.name : `Track ${index + 1}`,
      color: typeof track.color === "string" ? track.color : undefined,
      index,
      volume: Math.round((Number(track.amplitude) || 0) * 100),
      pan: Math.round((Number(track.balance) || 0) * 100),
      muted: Boolean(track.mute),
      solo: Boolean(track.solo),
      hidden: Boolean(track.hidden),
      clipIds,
    });
  });

  return { bpm, timeSignature: signature, tracks, lanes, markers: markersFromState(state.sections, bps) };
}

/** Short, readable suffix for ids created from a Suno id. */
function shortId(value: string): string {
  return value.replace(/-/g, "").slice(0, 10);
}

/**
 * Apply a Suno document to a local project ("Load Suno version").
 *
 * This is a merge, not a replace: tracks and clips are matched by the Suno id
 * they were pulled from (or the deterministic id their local id maps to), and
 * anything Suno does not know about — a local upload, a clip that has not been
 * uploaded yet — is kept rather than silently deleted. The caller is told what
 * was kept so the UI can explain the result.
 */
export function mergeSunoProjectIntoLocal(
  local: LocalDocument,
  suno: {
    bpm: number;
    timeSignature: string;
    tracks: LocalTrack[];
    lanes: LocalClip[];
    markers?: Array<{ id: string; time: number; label: string; color?: string }>;
  }
): { data: LocalDocument; keptLocalClips: string[]; droppedTracks: string[] } {
  const localTracks = Array.isArray(local.tracks) ? local.tracks : [];
  const localLanes = Array.isArray(local.lanes) ? local.lanes : [];
  const localTrackBySunoId = new Map<string, LocalTrack>();
  for (const track of localTracks) {
    localTrackBySunoId.set(track.sunoId ?? stableSunoId(track.id), track);
  }
  const localClipBySunoId = new Map<string, LocalClip>();
  for (const clip of localLanes) {
    localClipBySunoId.set(clip.sunoId ?? stableSunoId(clip.id), clip);
  }

  const usedTrackIds = new Set<string>();
  const usedClipIds = new Set<string>();
  const keptLocalClips: string[] = [];

  const tracks: LocalTrack[] = suno.tracks.map((track, index) => {
    const match =
      localTrackBySunoId.get(track.id) ??
      localTracks.find((candidate) => candidate.index === index && !candidate.sunoId);
    const id = match?.id ?? `track-${shortId(track.id)}`;
    usedTrackIds.add(match?.id ?? id);
    const clipIds: string[] = [];
    for (const sunoClip of suno.lanes.filter((clip) => clipIdsOf(track).includes(clip.id))) {
      const clipMatch = localClipBySunoId.get(sunoClip.id);
      const clipId = clipMatch?.id ?? `clip-${shortId(sunoClip.id)}`;
      usedClipIds.add(clipMatch?.id ?? clipId);
      clipIds.push(clipId);
      if (clipMatch) {
        clipMatch.title = sunoClip.title ?? clipMatch.title;
        clipMatch.color = sunoClip.color ?? clipMatch.color;
        clipMatch.start = sunoClip.start;
        clipMatch.duration = sunoClip.duration;
        clipMatch.midi = sunoClip.midi;
        clipMatch.sunoAssetId = sunoClip.sunoAssetId ?? clipMatch.sunoAssetId;
        clipMatch.sunoId = sunoClip.id;
      } else {
        localLanes.push({ ...sunoClip, id: clipId, sunoId: sunoClip.id });
      }
    }
    return {
      ...(match ?? {
        id,
        name: track.name ?? `Track ${index + 1}`,
        color: track.color,
        chain: [],
        index,
      }),
      sunoId: track.id,
      name: track.name ?? match?.name ?? `Track ${index + 1}`,
      color: track.color ?? match?.color,
      volume: track.volume,
      pan: track.pan,
      muted: track.muted,
      solo: track.solo,
      hidden: track.hidden,
      index,
      clipIds,
    };
  });

  // Local-only clips keep their place; drop a track only when it would be empty.
  const droppedTracks: string[] = [];
  const clipTrack = new Map<string, string>();
  for (const track of localTracks) {
    for (const clipId of track.clipIds ?? []) clipTrack.set(clipId, track.id);
  }
  for (const clip of localLanes) {
    if (usedClipIds.has(clip.id)) continue;
    keptLocalClips.push(clip.id);
    const ownerId = clipTrack.get(clip.id);
    const owner = tracks.find((track) => track.id === ownerId);
    if (owner) {
      owner.clipIds = [...new Set([...(owner.clipIds ?? []), clip.id])];
      continue;
    }
    const localOwner = localTracks.find((track) => (track.clipIds ?? []).includes(clip.id));
    if (localOwner && !usedTrackIds.has(localOwner.id)) {
      tracks.push({ ...localOwner, clipIds: [...new Set(localOwner.clipIds ?? [])] });
      usedTrackIds.add(localOwner.id);
    }
  }
  for (const track of localTracks) {
    if (!usedTrackIds.has(track.id) && (track.clipIds ?? []).length === 0) {
      droppedTracks.push(track.id);
    }
  }

  return {
    data: {
      ...local,
      tracks,
      lanes: localLanes,
      markers: suno.markers ?? local.markers,
    },
    keptLocalClips,
    droppedTracks,
  };
}

function clipIdsOf(track: LocalTrack): string[] {
  return (track.clipIds ?? []).filter((id): id is string => typeof id === "string");
}

/** Minimal document for a brand-new Suno project (title/metadata only). */export function emptySunoState(title: string, majorVersion = 2): Record<string, unknown> {
  const id = randomUUID();
  return {
    title,
    majorVersion,
    timing: { type: "manual", bps: 2, bpsAutomation: [], lockBPS: false },
    timeSignatureChanges: [
      { startBeats: 0, subdivisionsPerBar: 4, beatsPerSubdivision: 1 },
    ],
    amplitude: 1,
    songFadeInBeats: 0,
    songFadeOutBeats: 0,
    loop: { enabled: false, startBeats: 0, endBeats: 0 },
    metronome: { enabled: false, amplitude: 1 },
    editorPointerModes: { midi: "select", audio: "select" },
    tracks: [
      {
        id,
        name: "Track 1",
        color: "#7c5cff",
        type: "audio",
        height: 88,
        mute: false,
        solo: false,
        arm: false,
        hidden: false,
        amplitude: 0.8,
        balance: 0,
        routingMode: "stereo",
        signalChain: [],
        faderAutomation: [],
        clips: [],
        takeLanes: [],
        takeLanesExpanded: false,
        clipCreationIntents: [],
      },
    ],
    selection: {
      trackIds: [id],
      focusedTrackId: id,
      noteIds: [],
      anchorBeats: 0,
      focusBeats: 0,
      contextBeforeBeats: 32,
      contextAfterBeats: 32,
      focusedArea: "timeline",
      warpMarkerSeconds: {},
    },
  };
}
