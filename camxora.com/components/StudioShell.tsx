"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useSearchParams } from "next/navigation";

import { Icon } from "@/components/Icon";
import { clipTrackKey } from "@/lib/clip-utils";
import type { WebMusicGeneration } from "@/lib/library-api";
import {
  StudioSaveConflictError,
  WebMusicApiError,
  createStudioSession,
  exportStudioSession,
  fetchWebMusicLikedKeys,
  getStudioClip,
  getStudioClipDownload,
  getStudioSession,
  listWebMusicGenerations,
  resolveStudioClipId,
  resolveStudioClips,
  saveStudioSession,
} from "@/lib/web-music-api";

const BARS = 24;
const BEATS_PER_BAR = 4;
/** Suno's default tempo is `timing.bps = 2` (120 BPM); see docs/studio-state-schema.md. */
const DEFAULT_BPS = 2;
/** The visible ruler: 24 bars of 4 beats. Positions are stored in beats. */
const TIMELINE_BEATS = BARS * BEATS_PER_BAR;
const COLORS = ["#7466F1", "#A259FF", "#2f7bf6", "#25d366", "#f59e0b"];

type ClipRef = {
  uid: string;
  songId: string;
  variant: "ok" | "alt";
  /** Suno's provider clip id — what `state` stores as `asset.id`. */
  providerClipId?: string;
  /** Timeline position, in beats. */
  startBeats: number;
  /** Timeline length, in beats. */
  lengthBeats?: number;
  /** Offset into the source clip, in beats (trimmed head). */
  readStartBeats?: number;
  /** Fade lengths, in beats. */
  fadeInBeats?: number;
  fadeOutBeats?: number;
};

type Track = {
  id: string;
  /** Suno's track id once the track exists in the saved `state` document. */
  remoteId?: string;
  /** Provider clip ids this track had in the last document we read or wrote. */
  knownProviderIds?: string[];
  name: string;
  color: string;
  clips: ClipRef[];
  muted: boolean;
  solo: boolean;
  volume: number;
};

type PlacedClip = ClipRef & {
  trackId: string;
  /** Seconds from the start of the timeline. */
  start: number;
  /** Seconds into the source clip where playback begins. */
  readStart: number;
  /** Fade lengths in seconds. */
  fadeIn: number;
  fadeOut: number;
  duration: number;
  src: string;
};

type MixerEngine = {
  ctx: AudioContext;
  master: GainNode;
  tracks: Map<string, GainNode>;
  clips: Map<string, GainNode>;
  sources: Map<string, MediaElementAudioSourceNode>;
};

type SaveStatus = "idle" | "saving" | "saved" | "error" | "conflict";

type HistorySnapshot = { tracks: Track[]; masterVolume: number };

function clock(seconds: number) {
  const m = Math.floor(seconds / 60);
  const s = Math.floor(seconds % 60);
  const ms = Math.floor((seconds % 1) * 1000);
  return `${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}.${String(ms).padStart(3, "0")}`;
}

function newUid() {
  if (typeof crypto !== "undefined" && typeof crypto.randomUUID === "function") {
    return crypto.randomUUID();
  }
  return `id-${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

function chosenVariant(song?: WebMusicGeneration): "ok" | "alt" {
  const clip = song?.clips?.find((item) => item.ready) ?? song?.clips?.[0];
  return clip?.variant === "alt" ? "alt" : "ok";
}

function asRecord(value: unknown): Record<string, unknown> | null {
  return value && typeof value === "object" && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : null;
}

function readBps(state: Record<string, unknown> | null) {
  const timing = asRecord(state?.timing);
  const bps = timing?.bps;
  return typeof bps === "number" && Number.isFinite(bps) && bps > 0 ? bps : DEFAULT_BPS;
}

/** Track EQ default, captured from the editor bundle's `634615` module. */
function defaultEq() {
  const band = (
    type: string,
    enabled: boolean,
    frequency: number
  ): Record<string, unknown> => ({ type, enabled, frequency, gain: 0, q: 0.707 });
  return {
    enabled: true,
    band1: band("highpass", false, 60),
    band2: band("lowshelf", true, 160),
    band3: band("peaking", true, 450),
    band4: band("peaking", true, 1200),
    band5: band("highshelf", true, 3200),
    band6: band("lowpass", false, 8800),
  };
}

/** Audio-track defaults, captured from the editor bundle's `46472`/`634615` modules. */
function defaultTrackShape(id: string, color: string): Record<string, unknown> {
  return {
    type: "audio",
    id,
    input: null,
    color,
    name: "Audio Track",
    clips: [],
    clipCreationIntents: [],
    height: 86,
    solo: false,
    mute: false,
    arm: false,
    amplitude: 1,
    balance: 0,
    instrument: { type: "song" },
    soloTakeLaneId: null,
    takeLanesExpanded: false,
    hidden: false,
    takeLanes: [],
    eq: defaultEq(),
    signalChain: [],
    routingMode: "linear",
  };
}

/** Empty project document, captured from the editor bundle's `960687` module. */
function createDefaultState(): Record<string, unknown> {
  return {
    amplitude: 1,
    sections: {},
    lyricsCorrectionsByClipId: {},
    metronome: { enabled: false, amplitude: 1 },
    midiNotePreviewEnabled: true,
    timing: {
      type: "manual",
      bps: DEFAULT_BPS,
      bpsAutomation: [],
      firstBeatSeconds: 0,
    },
    timeSignatureChanges: [
      { startBeats: 0, subdivisionsPerBar: 4, beatsPerSubdivision: 1 },
    ],
    tracks: [],
    actors: {},
    tab: {
      selection: {
        anchorBeats: 0,
        focusBeats: 0,
        trackIds: [],
        focusedTrackId: null,
        focusedTakeLaneId: null,
        focusedArea: null,
        arrangementAnchorBeats: null,
        arrangementFocusBeats: null,
        noteIds: [],
        pluginIds: [],
        warpMarkerSeconds: {},
        automationPointIndices: [],
        contextBeforeBeats: 32,
        contextAfterBeats: 32,
      },
    },
    loop: { enabled: false, startBeats: 0, endBeats: 0 },
    songFadeInBeats: 0,
    songFadeOutBeats: 0,
    layout: {
      editorPanelType: null,
      midiAutomationLaneId: "none",
      midiAutomationLaneHeight: 0,
      arrangementEditorHeight: 0,
    },
    editorPointerModes: { audio: "select", midi: "select" },
    masterSignalChain: [],
    midiControllerSignalChain: [],
    masterRoutingMode: "linear",
    routing: {},
  };
}

/**
 * Rebuild the arrangement clip Suno expects. Shape captured from the shipped
 * editor bundle (`createStaticAudioArrangement`, see docs/studio-state-schema.md).
 */
function buildClip(
  clip: ClipRef,
  track: Track,
  songs: Map<string, WebMusicGeneration>,
  placed: Map<string, PlacedClip>,
  bps: number
): Record<string, unknown> | null {
  if (!clip.providerClipId) return null;
  const startBeats = Math.max(0, clip.startBeats);
  const seconds = placed.get(clip.uid)?.duration;
  const lengthBeats =
    clip.lengthBeats ?? (seconds && seconds > 0 ? Math.round(seconds * bps) : 8);
  return {
    type: "audio",
    id: clip.uid,
    streaming: false,
    name: songs.get(clip.songId)?.title || "Clip",
    color: track.color,
    transposition: 0,
    formantCorrection: 0,
    amplitude: 1,
    startBeats,
    endBeats: startBeats + Math.max(1, lengthBeats),
    readStartBeats: Math.max(0, clip.readStartBeats ?? 0),
    fadeInBeats: Math.min(Math.max(0, clip.fadeInBeats ?? 0), Math.max(1, lengthBeats)),
    fadeOutBeats: Math.min(Math.max(0, clip.fadeOutBeats ?? 0), Math.max(1, lengthBeats)),
    fadeInCurve: 1,
    fadeOutCurve: 1,
    mute: false,
    reversed: false,
    loop: { enabled: false, startBeats: 0, endBeats: 0 },
    warp: { awaitingAnalysis: false, enabled: true, markers: {} },
    asset: { type: "clip", id: clip.providerClipId },
  };
}

/**
 * Merge the local arrangement into the `state` document last read from Suno.
 * Unknown fields (eq, instrument, signal chains, sections, routing, …) are kept
 * from that document — we only own track mixer values and audio clips.
 */
function buildProjectState(input: {
  base: Record<string, unknown>;
  tracks: Track[];
  masterVolume: number;
  songs: Map<string, WebMusicGeneration>;
  placed: Map<string, PlacedClip>;
  bps: number;
  metronome: boolean;
  metronomeVolume: number;
}): Record<string, unknown> | null {
  const baseTracks = Array.isArray(input.base.tracks)
    ? (input.base.tracks as unknown[])
        .map(asRecord)
        .filter((track): track is Record<string, unknown> => Boolean(track))
    : [];
  const baseAudio = baseTracks.filter((track) => track.type === "audio");
  const byId = new Map(baseTracks.map((track) => [String(track.id ?? ""), track]));
  const claimed = new Set<string>();
  const out: Record<string, unknown>[] = [];

  for (const [index, track] of input.tracks.entries()) {
    // Match by id first, then by position. Anything else is a brand-new lane and
    // gets the captured default track shape.
    let source = (track.remoteId && byId.get(track.remoteId)) || null;
    if (!source) {
      const candidate = baseAudio[index];
      if (candidate && !claimed.has(String(candidate.id ?? ""))) source = candidate;
    }
    const synthetic = !source;
    if (!source) {
      source = defaultTrackShape(track.remoteId ?? newUid(), track.color);
    }
    const sourceId = String(source.id ?? "");
    const sourceAlreadyClaimed = claimed.has(sourceId);
    if (!synthetic) claimed.add(sourceId);

    const clips = Array.isArray(source.clips) ? (source.clips as unknown[]) : [];
    const known = new Set(track.knownProviderIds ?? []);
    const local = new Set(
      track.clips
        .map((clip) => clip.providerClipId)
        .filter((id): id is string => Boolean(id))
    );
    // Keep clips we do not model (MIDI, uploads, video) and audio clips we never
    // mapped to a song. Mapped clips are rebuilt from the local arrangement, so a
    // clip the user deleted here disappears; an unknown one is left untouched.
    const kept = synthetic
      ? []
      : clips
          .map(asRecord)
          .filter((clip): clip is Record<string, unknown> => Boolean(clip))
          .filter((clip) => {
            if (clip.type !== "audio") return true;
            const asset = asRecord(clip.asset);
            if (asset?.type !== "clip" || typeof asset.id !== "string") return true;
            return !known.has(asset.id) && !local.has(asset.id);
          });
    const ours = track.clips
      .map((clip) =>
        buildClip(clip, track, input.songs, input.placed, input.bps)
      )
      .filter((clip): clip is Record<string, unknown> => Boolean(clip));
    out.push({
      ...source,
      id:
        track.remoteId && byId.has(track.remoteId)
          ? track.remoteId
          : sourceAlreadyClaimed
            ? newUid()
            : sourceId || newUid(),
      type: "audio",
      name: track.name,
      color: track.color,
      amplitude: track.volume / 100,
      balance: typeof source.balance === "number" ? source.balance : 0,
      solo: track.solo,
      mute: track.muted,
      arm: false,
      clips: [...kept, ...ours],
    });
  }

  // Never write a document that would silently drop a track we could not match.
  if (baseAudio.some((track) => !claimed.has(String(track.id ?? "")))) return null;

  const baseMetronome = asRecord(input.base.metronome) ?? {};
  return {
    ...input.base,
    amplitude: input.masterVolume / 100,
    metronome: {
      ...baseMetronome,
      enabled: input.metronome,
      amplitude: input.metronomeVolume,
    },
    tracks: out,
  };
}

/**
 * Suno's project view: track panel on the left, bar-numbered timeline in the
 * middle, prompt bar along the bottom, transport in the header.
 *
 * Playback is a real mixer: one stream per placed clip, each routed through its
 * track's gain into the master strip, so volume / mute / solo / Main all change
 * what you hear. Arrangement positions live in beats, matching Suno's `state`
 * document, and are autosaved back through `save-project`.
 */
export function StudioShell() {
  const params = useSearchParams();
  const projectParam = params.get("project");

  const [songs, setSongs] = useState<WebMusicGeneration[]>([]);
  const [tracks, setTracks] = useState<Track[]>([]);
  const [selectedTrack, setSelectedTrack] = useState<string | null>(null);
  const [selectedClip, setSelectedClip] = useState<string | null>(null);
  const [clipMenu, setClipMenu] = useState<{
    uid: string;
    x: number;
    y: number;
  } | null>(null);
  const dragRef = useRef<{
    uid: string;
    startX: number;
    startBeat: number;
    laneWidth: number;
  } | null>(null);
  const trimRef = useRef<{
    uid: string;
    edge: "start" | "end";
    startX: number;
    startBeats: number;
    lengthBeats: number;
    readStartBeats: number;
    laneWidth: number;
  } | null>(null);
  const fadeRef = useRef<{
    uid: string;
    edge: "in" | "out";
    startX: number;
    fadeBeats: number;
    lengthBeats: number;
    laneWidth: number;
  } | null>(null);
  const [projectName, setProjectName] = useState("Untitled Project");
  const [projectId, setProjectId] = useState<string | null>(projectParam);
  const [libraryOpen, setLibraryOpen] = useState(false);
  const [libraryTab, setLibraryTab] = useState<"songs" | "liked">("songs");
  const [likedKeys, setLikedKeys] = useState<string[]>([]);
  const [playing, setPlaying] = useState(false);
  const [position, setPosition] = useState(0);
  const [zoom, setZoom] = useState(1);
  const [masterVolume, setMasterVolume] = useState(100);
  const [metronome, setMetronome] = useState(false);
  const [bps, setBps] = useState(DEFAULT_BPS);
  const [hydrating, setHydrating] = useState(Boolean(projectParam));
  const [saving, setSaving] = useState(false);
  const [saveStatus, setSaveStatus] = useState<SaveStatus>("idle");
  const [exporting, setExporting] = useState(false);
  const [exportStatus, setExportStatus] = useState("");
  const [prompt, setPrompt] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  /** A clip stream the browser could not play (e.g. encrypted playback). */
  const [playbackIssue, setPlaybackIssue] = useState(false);
  /** Durations reported by the media elements, keyed `songId:variant`. */
  const [measured, setMeasured] = useState<Record<string, number>>({});

  const audioHostRef = useRef<HTMLDivElement | null>(null);
  const elementsRef = useRef<Map<string, HTMLAudioElement>>(new Map());
  const engineRef = useRef<MixerEngine | null>(null);
  const loopRef = useRef<number | null>(null);
  const clockRef = useRef<HTMLSpanElement | null>(null);
  const barRef = useRef<HTMLSpanElement | null>(null);
  const playheadRef = useRef<HTMLDivElement | null>(null);
  /** Clips that were inside the transport window on the previous tick. */
  const windowRef = useRef<Set<string>>(new Set());
  /** Authoritative transport position: `at` while paused, `from` while playing. */
  const transport = useRef({ at: 0, from: 0, playing: false });
  /** Undo/redo over the arrangement and main fader (60 steps). */
  const history = useRef<{ stack: HistorySnapshot[]; index: number }>({
    stack: [],
    index: -1,
  });
  const applyingHistory = useRef(false);
  const [historyTick, setHistoryTick] = useState(0);
  /** Last `state` document read from Suno; autosave merges into it. */
  const baseStateRef = useRef<Record<string, unknown> | null>(null);
  /** Latest saved version, sent as `base_version_id`. */
  const versionRef = useRef<string | null>(null);
  /** Snapshot of what the server already has, so idle renders do not save. */
  const savedSnapshotRef = useRef("");
  const bpsRef = useRef(bps);
  bpsRef.current = bps;
  const timelineSecondsRef = useRef(TIMELINE_BEATS / bps);
  timelineSecondsRef.current = TIMELINE_BEATS / bps;

  const songsById = useMemo(
    () => new Map(songs.map((song) => [song.id, song])),
    [songs]
  );

  const placed = useMemo(() => {
    const map = new Map<string, PlacedClip>();
    const secondsPerBeat = 1 / bps;
    tracks.forEach((track) => {
      track.clips.forEach((clip) => {
        const song = songsById.get(clip.songId);
        const start = Math.min(
          Math.max(0, clip.startBeats) * secondsPerBeat,
          Math.max(0, TIMELINE_BEATS / bps - 0.5)
        );
        const key = `${clip.songId}:${clip.variant}`;
        const declared = song?.clips?.find((item) => item.variant === clip.variant)
          ?.duration_seconds;
        const known = measured[key] ?? declared ?? null;
        const length =
          clip.lengthBeats && clip.lengthBeats > 0
            ? clip.lengthBeats * secondsPerBeat
            : known && known > 0
              ? known
              : TIMELINE_BEATS / bps - start;
        const duration = Math.min(length, TIMELINE_BEATS / bps - start);
        const declaredUrl = song?.clips?.find(
          (item) => item.variant === clip.variant
        )?.audio_url;
        // Same-origin only: a cross-origin URL without CORS yields silence when
        // tapped into the audio graph, so use our stream proxy otherwise.
        const sameOrigin =
          declaredUrl &&
          (declaredUrl.startsWith("/") ||
            (typeof window !== "undefined" &&
              declaredUrl.startsWith(window.location.origin)));
        const src = sameOrigin
          ? declaredUrl
          : `/api/v3/web-music/generations/${clip.songId}/stream/${clip.variant}`;
        map.set(clip.uid, {
          ...clip,
          trackId: track.id,
          start,
          readStart: Math.max(0, clip.readStartBeats ?? 0) * secondsPerBeat,
          fadeIn: Math.max(0, clip.fadeInBeats ?? 0) * secondsPerBeat,
          fadeOut: Math.max(0, clip.fadeOutBeats ?? 0) * secondsPerBeat,
          duration,
          src,
        });
      });
    });
    return map;
  }, [tracks, songsById, measured, bps]);

  /** Everything the imperative transport loop needs, kept current each render. */
  const live = useRef({ tracks, placed, masterVolume, bps, metronome });
  live.current = { tracks, placed, masterVolume, bps, metronome };
  /** Metronome click level, preserved from the project state (default 1). */
  const metronomeVolumeRef = useRef(1);
  /** Beats per bar for the metronome accent (state.timeSignatureChanges). */
  const beatsPerBarRef = useRef(BEATS_PER_BAR);
  /** Last beat that already produced a click. */
  const lastClickBeatRef = useRef(-1);

  useEffect(() => {
    let active = true;
    listWebMusicGenerations(50)
      .then((page) => {
        if (active) setSongs(page.items);
      })
      .catch(() => {
        if (active) setError("Could not load your songs");
      });
    return () => {
      active = false;
    };
  }, []);

  // Hydrate the arrangement from Suno's project document.
  useEffect(() => {
    if (!projectParam) return;
    let active = true;
    setProjectId(projectParam);
    setHydrating(true);
    setPlaybackIssue(false);
    getStudioSession(projectParam)
      .then(async (session) => {
        if (!active) return;
        const title = typeof session.title === "string" ? session.title : null;
        if (title) setProjectName(title);
        const doc = asRecord(session.state) ?? createDefaultState();
        baseStateRef.current = doc;
        versionRef.current =
          typeof session.latest_version_id === "string"
            ? session.latest_version_id
            : null;
        const nextBps = readBps(doc);
        setBps(nextBps);
        const nextMaster =
          typeof doc.amplitude === "number"
            ? Math.round(Math.min(1, Math.max(0, doc.amplitude)) * 100)
            : 100;
        setMasterVolume(nextMaster);
        const metronomeState = asRecord(doc.metronome);
        setMetronome(Boolean(metronomeState?.enabled));
        if (typeof metronomeState?.amplitude === "number") {
          metronomeVolumeRef.current = Math.min(
            1,
            Math.max(0, metronomeState.amplitude)
          );
        }
        // `timeSignatureChanges` is a list of `{ startBeats, subdivisionsPerBar,
        // beatsPerSubdivision }`; the first entry anchors the bar length.
        const signatures = Array.isArray(doc.timeSignatureChanges)
          ? (doc.timeSignatureChanges as unknown[])
              .map(asRecord)
              .filter((item): item is Record<string, unknown> => Boolean(item))
          : [];
        const first = signatures[0];
        const subdivisions = Number(first?.subdivisionsPerBar) || BEATS_PER_BAR;
        const perSubdivision = Number(first?.beatsPerSubdivision) || 1;
        beatsPerBarRef.current = Math.max(
          1,
          Math.round(subdivisions * perSubdivision)
        );

        const stateTracks = (Array.isArray(doc.tracks) ? doc.tracks : [])
          .map(asRecord)
          .filter((track): track is Record<string, unknown> => Boolean(track))
          .filter((track) => track.type === "audio" && !track.hidden);

        const providerIds: string[] = [];
        stateTracks.forEach((track) => {
          (Array.isArray(track.clips) ? track.clips : [])
            .map(asRecord)
            .forEach((clip) => {
              const asset = asRecord(clip?.asset);
              if (asset?.type === "clip" && typeof asset.id === "string") {
                providerIds.push(asset.id);
              }
            });
        });
        const resolved = providerIds.length
          ? await resolveStudioClips(providerIds).catch(() => [])
          : [];
        if (!active) return;
        const byClip = new Map(resolved.map((hit) => [hit.clip_id, hit]));

        const nextTracks: Track[] = [];
        stateTracks.forEach((track, index) => {
          const remoteId = typeof track.id === "string" ? track.id : newUid();
          const clips: ClipRef[] = [];
          const trackClips = (Array.isArray(track.clips) ? track.clips : [])
            .map(asRecord)
            .filter((clip): clip is Record<string, unknown> => Boolean(clip));
          const knownProviderIds = trackClips
            .map((clip) => {
              const asset = asRecord(clip.asset);
              return asset?.type === "clip" && typeof asset.id === "string"
                ? asset.id
                : null;
            })
            .filter((id): id is string => Boolean(id));
          trackClips.forEach((clip) => {
            const asset = asRecord(clip.asset);
            const assetId =
              asset?.type === "clip" && typeof asset.id === "string"
                ? asset.id
                : null;
            if (!assetId) return;
            const hit = byClip.get(assetId);
            // A clip we cannot map to one of our songs stays untouched on
            // Suno; we simply cannot play or resave it.
            if (!hit) return;
            const startBeats = Number(clip.startBeats) || 0;
            const endBeats = Number(clip.endBeats) || startBeats;
            clips.push({
              uid: typeof clip.id === "string" ? clip.id : newUid(),
              songId: hit.task_id,
              variant: hit.variant,
              providerClipId: assetId,
              startBeats,
              lengthBeats: Math.max(1, endBeats - startBeats),
              readStartBeats: Number(clip.readStartBeats) || 0,
              fadeInBeats: Number(clip.fadeInBeats) || 0,
              fadeOutBeats: Number(clip.fadeOutBeats) || 0,
            });
          });
          nextTracks.push({
            id: remoteId,
            remoteId,
            knownProviderIds,
            name:
              typeof track.name === "string" && track.name
                ? track.name
                : `Track ${index + 1}`,
            color:
              typeof track.color === "string" && track.color
                ? track.color
                : COLORS[index % COLORS.length],
            clips,
            muted: Boolean(track.mute),
            solo: Boolean(track.solo),
            volume:
              typeof track.amplitude === "number"
                ? Math.round(Math.min(1, Math.max(0, track.amplitude)) * 100)
                : 100,
          });
        });
        if (nextTracks.length) setTracks(nextTracks);
        history.current = {
          stack: [
            {
              tracks: nextTracks.length ? nextTracks : tracks,
              masterVolume: nextMaster,
            },
          ],
          index: 0,
        };
        setHistoryTick((value) => value + 1);
        // Baseline exactly what we just loaded so hydration never autosaves.
        savedSnapshotRef.current = JSON.stringify({
          tracks: nextTracks.length ? nextTracks : tracks,
          masterVolume: nextMaster,
          projectName: title ?? "Untitled Project",
          metronome: Boolean(metronomeState?.enabled),
        });
      })
      .catch(() => {
        /* older project or a signed-out pool: keep the id we have */
      })
      .finally(() => {
        if (active) setHydrating(false);
      });
    return () => {
      active = false;
    };
    // `tracks`, `masterVolume` and `projectName` are read only for the snapshot
    // baseline; hydrating again on their change would clobber local edits.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [projectParam]);

  const currentPosition = useCallback(() => {
    const engine = engineRef.current;
    if (!engine || !transport.current.playing) return transport.current.at;
    return transport.current.at + (engine.ctx.currentTime - transport.current.from);
  }, []);

  const updateView = useCallback((seconds: number) => {
    if (clockRef.current) clockRef.current.textContent = clock(seconds);
    if (barRef.current) {
      const beat = seconds * bpsRef.current;
      const bar = Math.max(1, Math.floor(beat / BEATS_PER_BAR) + 1);
      const beatInBar = Math.floor(beat % BEATS_PER_BAR) + 1;
      barRef.current.textContent = `${String(bar).padStart(3, "0")}.${beatInBar}.1`;
    }
    if (playheadRef.current) {
      playheadRef.current.style.left = `${(seconds / timelineSecondsRef.current) * 100}%`;
    }
  }, []);

  const stopLoop = useCallback(() => {
    if (loopRef.current !== null) {
      cancelAnimationFrame(loopRef.current);
      loopRef.current = null;
    }
  }, []);

  /** Clip gain carries the fade curve; track and Main gains stay untouched. */
  const scheduleClipGain = useCallback(
    (engine: MixerEngine, uid: string, clip: PlacedClip, local: number) => {
      const gain = engine.clips.get(uid);
      if (!gain) return;
      const now = engine.ctx.currentTime;
      const fadeIn = Math.max(0, Math.min(clip.fadeIn, clip.duration));
      const fadeOut = Math.max(0, Math.min(clip.fadeOut, clip.duration));
      const remaining = Math.max(0, clip.duration - local);
      gain.gain.cancelScheduledValues(now);
      if (fadeIn > 0 && local < fadeIn) {
        gain.gain.setValueAtTime(Math.min(1, local / fadeIn), now);
        gain.gain.linearRampToValueAtTime(1, now + (fadeIn - local));
      } else {
        gain.gain.setValueAtTime(1, now);
      }
      if (fadeOut > 0) {
        if (remaining <= fadeOut) {
          gain.gain.setValueAtTime(Math.min(1, remaining / fadeOut), now);
          gain.gain.linearRampToValueAtTime(0, now + remaining);
        } else {
          const fadeStart = now + (remaining - fadeOut);
          gain.gain.setValueAtTime(1, fadeStart);
          gain.gain.linearRampToValueAtTime(0, now + remaining);
        }
      }
    },
    []
  );

  /** Short click on the metronome bus; downbeats are higher pitched. */
  const playClick = useCallback((engine: MixerEngine, downbeat: boolean) => {
    const now = engine.ctx.currentTime;
    const osc = engine.ctx.createOscillator();
    const gain = engine.ctx.createGain();
    osc.type = "square";
    osc.frequency.value = downbeat ? 1600 : 1000;
    gain.gain.setValueAtTime(
      0.25 * metronomeVolumeRef.current,
      now
    );
    gain.gain.exponentialRampToValueAtTime(0.0001, now + 0.05);
    osc.connect(gain);
    gain.connect(engine.master);
    osc.start(now);
    osc.stop(now + 0.06);
  }, []);

  /** Start/stop each placed clip so it matches the transport window. */
  const syncClips = useCallback(
    (seconds: number, shouldPlay: boolean, force: boolean) => {
      const placedNow = live.current.placed;
      const insideNow = new Set<string>();
      elementsRef.current.forEach((el, uid) => {
        const clip = placedNow.get(uid);
        const inside = clip
          ? seconds >= clip.start && seconds < clip.start + clip.duration
          : false;
        if (!inside) {
          if (!el.paused) el.pause();
          return;
        }
        insideNow.add(uid);
        if (!shouldPlay) return;
        // Only (re)start on entry or an explicit seek: retrying every frame
        // would replay a clip that ended, or hammer a stream that failed.
        if (!force && windowRef.current.has(uid)) return;
        try {
          el.currentTime = (clip?.readStart ?? 0) + (seconds - (clip?.start ?? 0));
        } catch {
          /* metadata not ready yet: the next entry retries */
        }
        void el.play().catch(() => undefined);
        const engine = engineRef.current;
        if (engine && clip) {
          scheduleClipGain(engine, uid, clip, seconds - clip.start);
        }
      });
      windowRef.current = insideNow;
    },
    [scheduleClipGain]
  );

  const trackGain = useCallback((engine: MixerEngine, trackId: string) => {
    const existing = engine.tracks.get(trackId);
    if (existing) return existing;
    const gain = engine.ctx.createGain();
    gain.gain.value = 1;
    gain.connect(engine.master);
    engine.tracks.set(trackId, gain);
    return gain;
  }, []);

  const applyGains = useCallback(
    (engine: MixerEngine, liveTracks: Track[], master: number) => {
      const now = engine.ctx.currentTime;
      engine.master.gain.setTargetAtTime(master / 100, now, 0.015);
      const alive = new Set(liveTracks.map((track) => track.id));
      engine.tracks.forEach((gain, id) => {
        if (alive.has(id)) return;
        gain.disconnect();
        engine.tracks.delete(id);
      });
      const anySolo = liveTracks.some((track) => track.solo);
      liveTracks.forEach((track) => {
        const gain = trackGain(engine, track.id);
        const audible = !track.muted && (!anySolo || track.solo);
        gain.gain.setTargetAtTime(audible ? track.volume / 100 : 0, now, 0.015);
      });
    },
    [trackGain]
  );

  const attachSource = useCallback(
    (engine: MixerEngine, uid: string, el: HTMLAudioElement, trackId: string) => {
      if (engine.sources.has(uid)) return;
      try {
        const source = engine.ctx.createMediaElementSource(el);
        const gain = engine.ctx.createGain();
        gain.gain.value = 1;
        source.connect(gain);
        gain.connect(trackGain(engine, trackId));
        engine.clips.set(uid, gain);
        engine.sources.set(uid, source);
      } catch {
        /* element already wired into another graph */
      }
    },
    [trackGain]
  );

  const ensureEngine = useCallback(() => {
    if (engineRef.current) return engineRef.current;
    const Ctor =
      window.AudioContext ??
      (window as unknown as { webkitAudioContext?: typeof AudioContext })
        .webkitAudioContext;
    if (!Ctor) return null;
    const ctx = new Ctor();
    const master = ctx.createGain();
    master.gain.value = live.current.masterVolume / 100;
    master.connect(ctx.destination);
    engineRef.current = {
      ctx,
      master,
      tracks: new Map(),
      clips: new Map(),
      sources: new Map(),
    };
    return engineRef.current;
  }, []);

  const pause = useCallback(() => {
    const at = Math.min(
      timelineSecondsRef.current,
      Math.max(0, currentPosition())
    );
    transport.current.at = at;
    transport.current.playing = false;
    stopLoop();
    elementsRef.current.forEach((el) => el.pause());
    const engine = engineRef.current;
    if (engine) {
      const now = engine.ctx.currentTime;
      engine.clips.forEach((gain) => {
        gain.gain.cancelScheduledValues(now);
        gain.gain.setValueAtTime(1, now);
      });
    }
    setPlaying(false);
    setPosition(at);
    updateView(at);
  }, [currentPosition, stopLoop, updateView]);

  const start = useCallback(async () => {
    const engine = ensureEngine();
    if (!engine) return;
    applyGains(engine, live.current.tracks, live.current.masterVolume);
    live.current.placed.forEach((clip, uid) => {
      const el = elementsRef.current.get(uid);
      if (el) attachSource(engine, uid, el, clip.trackId);
    });
    try {
      await engine.ctx.resume();
    } catch {
      /* resume needs a user gesture; the click provides one */
    }
    if (transport.current.at >= timelineSecondsRef.current) transport.current.at = 0;
    transport.current.playing = true;
    transport.current.from = engine.ctx.currentTime;
    setPlaying(true);
    syncClips(transport.current.at, true, true);

    stopLoop();
    lastClickBeatRef.current = -1;
    const step = () => {
      const running = engineRef.current;
      if (!running || !transport.current.playing) return;
      const seconds = currentPosition();
      updateView(seconds);
      syncClips(seconds, true, false);
      const beat = Math.floor(seconds * live.current.bps);
      if (live.current.metronome && beat > lastClickBeatRef.current) {
        lastClickBeatRef.current = beat;
        playClick(running, beat % Math.max(1, beatsPerBarRef.current) === 0);
      } else if (!live.current.metronome && beat !== lastClickBeatRef.current) {
        lastClickBeatRef.current = beat;
      }
      if (seconds >= timelineSecondsRef.current) {
        pause();
        return;
      }
      loopRef.current = requestAnimationFrame(step);
    };
    loopRef.current = requestAnimationFrame(step);
  }, [
    applyGains,
    attachSource,
    currentPosition,
    ensureEngine,
    pause,
    playClick,
    stopLoop,
    syncClips,
    updateView,
  ]);

  /** A clip was dropped at a new spot: re-arm it if the transport is running. */
  const endDrag = useCallback(() => {
    const dragging = dragRef.current ?? trimRef.current ?? fadeRef.current;
    dragRef.current = null;
    trimRef.current = null;
    fadeRef.current = null;
    if (dragging && transport.current.playing) {
      syncClips(currentPosition(), true, true);
    }
  }, [currentPosition, syncClips]);

  const updateClip = useCallback((uid: string, patch: Partial<ClipRef>) => {
    setTracks((current) =>
      current.map((track) => ({
        ...track,
        clips: track.clips.map((clip) =>
          clip.uid === uid ? { ...clip, ...patch } : clip
        ),
      }))
    );
  }, []);

  const removeClip = useCallback((uid: string) => {
    setTracks((current) =>
      current.map((track) => ({
        ...track,
        clips: track.clips.filter((clip) => clip.uid !== uid),
      }))
    );
    setSelectedClip((current) => (current === uid ? null : current));
    setClipMenu((current) => (current?.uid === uid ? null : current));
  }, []);

  const clipLength = useCallback(
    (clip: ClipRef) => Math.max(1, clip.lengthBeats ?? 8),
    []
  );

  /** Copy a clip to the right of itself, keeping its trim. */
  const duplicateClip = useCallback(
    (uid: string) => {
      setTracks((current) =>
        current.map((track) => {
          const clip = track.clips.find((item) => item.uid === uid);
          if (!clip) return track;
          const length = Math.max(1, clip.lengthBeats ?? 8);
          const copy: ClipRef = {
            ...clip,
            uid: newUid(),
            startBeats: Math.min(
              TIMELINE_BEATS - 1,
              clip.startBeats + length
            ),
          };
          return { ...track, clips: [...track.clips, copy] };
        })
      );
    },
    []
  );

  /** Split a clip at the playhead into two arrangements sharing one source. */
  const splitClip = useCallback(
    (uid: string) => {
      const beat = Math.round(currentPosition() * bpsRef.current);
      setTracks((current) =>
        current.map((track) => {
          const clip = track.clips.find((item) => item.uid === uid);
          if (!clip) return track;
          const length = Math.max(1, clip.lengthBeats ?? 8);
          const end = clip.startBeats + length;
          if (beat <= clip.startBeats || beat >= end) return track;
          const readStart = Math.max(0, clip.readStartBeats ?? 0);
          const fadeIn = Math.min(Math.max(1, clip.lengthBeats ?? 8), Math.max(0, clip.fadeInBeats ?? 0));
          const fadeOut = Math.min(Math.max(1, clip.lengthBeats ?? 8), Math.max(0, clip.fadeOutBeats ?? 0));
          const left: ClipRef = {
            ...clip,
            lengthBeats: beat - clip.startBeats,
            fadeInBeats: Math.min(fadeIn, beat - clip.startBeats),
            fadeOutBeats: 0,
          };
          const right: ClipRef = {
            ...clip,
            uid: newUid(),
            startBeats: beat,
            lengthBeats: end - beat,
            readStartBeats: readStart + (beat - clip.startBeats),
            fadeInBeats: 0,
            fadeOutBeats: Math.min(fadeOut, end - beat),
          };
          return {
            ...track,
            clips: track.clips.flatMap((item) =>
              item.uid === uid ? [left, right] : [item]
            ),
          };
        })
      );
    },
    [currentPosition]
  );

  const seek = useCallback(
    (seconds: number) => {
      const next = Math.min(
        timelineSecondsRef.current,
        Math.max(0, seconds)
      );
      transport.current.at = next;
      const engine = engineRef.current;
      if (engine) transport.current.from = engine.ctx.currentTime;
      elementsRef.current.forEach((el) => el.pause());
      syncClips(next, transport.current.playing, true);
      setPosition(next);
      updateView(next);
    },
    [syncClips, updateView]
  );

  // Audio elements are created imperatively so the graph survives re-renders
  // (`createMediaElementSource` is one-shot per element).
  useEffect(() => {
    const host = audioHostRef.current;
    if (!host) return;
    elementsRef.current.forEach((el, uid) => {
      if (placed.has(uid)) return;
      el.pause();
      engineRef.current?.sources.get(uid)?.disconnect();
      engineRef.current?.sources.delete(uid);
      engineRef.current?.clips.get(uid)?.disconnect();
      engineRef.current?.clips.delete(uid);
      el.remove();
      elementsRef.current.delete(uid);
    });
    placed.forEach((clip, uid) => {
      let el = elementsRef.current.get(uid);
      if (!el) {
        const created = document.createElement("audio");
        created.preload = "auto";
        created.dataset.clipKey = `${clip.songId}:${clip.variant}`;
        created.addEventListener("loadedmetadata", () => {
          if (!created.isConnected || !Number.isFinite(created.duration)) return;
          const key = created.dataset.clipKey;
          if (!key) return;
          const duration = created.duration;
          setMeasured((current) =>
            Math.abs((current[key] ?? 0) - duration) < 0.05
              ? current
              : { ...current, [key]: duration }
          );
        });
        created.addEventListener("error", () => setPlaybackIssue(true));
        host.appendChild(created);
        elementsRef.current.set(uid, created);
        el = created;
      }
      if (el.getAttribute("src") !== clip.src) el.setAttribute("src", clip.src);
      const engine = engineRef.current;
      if (engine) attachSource(engine, uid, el, clip.trackId);
    });
    if (transport.current.playing) {
      syncClips(currentPosition(), true, false);
    }
  }, [placed, attachSource, currentPosition, syncClips]);

  // Volume / mute / solo / Main only move gain nodes; nothing reloads.
  useEffect(() => {
    const engine = engineRef.current;
    if (!engine) return;
    applyGains(engine, tracks, masterVolume);
  }, [applyGains, tracks, masterVolume]);

  useEffect(
    () => () => {
      stopLoop();
      elementsRef.current.forEach((el) => el.pause());
      const engine = engineRef.current;
      engineRef.current = null;
      if (engine) void engine.ctx.close().catch(() => undefined);
    },
    [stopLoop]
  );

  /** One versioned save, debounced by the effect below. */
  const saveNow = useCallback(async () => {
    const base = baseStateRef.current;
    if (!projectId || !base) return;
    const state = buildProjectState({
      base,
      tracks: live.current.tracks,
      masterVolume: live.current.masterVolume,
      songs: songsById,
      placed: live.current.placed,
      bps: live.current.bps,
      metronome: live.current.metronome,
      metronomeVolume: metronomeVolumeRef.current,
    });
    if (!state) {
      setSaveStatus("error");
      setError("This project cannot be saved from the current arrangement.");
      return;
    }
    const snapshot = JSON.stringify({
      tracks: live.current.tracks,
      masterVolume: live.current.masterVolume,
      projectName,
      metronome: live.current.metronome,
    });
    setSaving(true);
    setSaveStatus("saving");
    try {
      const { version_id } = await saveStudioSession({
        projectId,
        state,
        title: projectName,
        baseVersionId: versionRef.current,
      });
      versionRef.current = version_id;
      baseStateRef.current = state;
      savedSnapshotRef.current = snapshot;
      setSaveStatus("saved");
      setError("");
    } catch (cause) {
      if (cause instanceof StudioSaveConflictError) {
        // Someone else saved first: adopt their version and try once more.
        versionRef.current = cause.latestVersionId;
        setSaveStatus("conflict");
        try {
          const { version_id } = await saveStudioSession({
            projectId,
            state,
            title: projectName,
            baseVersionId: versionRef.current,
          });
          versionRef.current = version_id;
          baseStateRef.current = state;
          savedSnapshotRef.current = snapshot;
          setSaveStatus("saved");
        } catch {
          setSaveStatus("error");
          setError("Someone else is editing this project. Reload to catch up.");
        }
      } else if (cause instanceof WebMusicApiError && cause.status === 429) {
        setSaveStatus("error");
        setError("Saving too often. Retrying shortly.");
        window.setTimeout(() => void saveNowRef.current(), (cause.retryAfterSeconds ?? 5) * 1000);
      } else {
        setSaveStatus("error");
        setError(cause instanceof Error ? cause.message : "Could not save the project");
      }
    } finally {
      setSaving(false);
    }
  }, [projectId, projectName, songsById]);
  const saveNowRef = useRef(saveNow);
  saveNowRef.current = saveNow;

  // Autosave: 3 s after the last edit, only once a real state document exists.
  useEffect(() => {
    if (!projectId || hydrating || !baseStateRef.current) return;
    const snapshot = JSON.stringify({
      tracks,
      masterVolume,
      projectName,
      metronome,
    });
    if (snapshot === savedSnapshotRef.current) return;
    const timer = window.setTimeout(() => void saveNowRef.current(), 3000);
    return () => window.clearTimeout(timer);
  }, [tracks, masterVolume, projectName, projectId, hydrating, metronome]);

  // Record settled edits so undo/redo can walk them back.
  useEffect(() => {
    if (hydrating) return;
    if (applyingHistory.current) {
      applyingHistory.current = false;
      return;
    }
    const snapshot: HistorySnapshot = { tracks, masterVolume };
    const timer = window.setTimeout(() => {
      const state = history.current;
      const current = state.stack[state.index];
      if (current && JSON.stringify(current) === JSON.stringify(snapshot)) return;
      state.stack = state.stack.slice(0, state.index + 1);
      state.stack.push(snapshot);
      if (state.stack.length > 60) state.stack.shift();
      state.index = state.stack.length - 1;
      setHistoryTick((value) => value + 1);
    }, 450);
    return () => window.clearTimeout(timer);
  }, [tracks, masterVolume, hydrating]);

  const canUndo = history.current.index > 0;
  const canRedo =
    history.current.index >= 0 &&
    history.current.index < history.current.stack.length - 1;
  void historyTick;

  const applyHistory = useCallback((index: number) => {
    const state = history.current;
    const snapshot = state.stack[index];
    if (!snapshot) return;
    state.index = index;
    applyingHistory.current = true;
    setTracks(snapshot.tracks);
    setMasterVolume(snapshot.masterVolume);
    setHistoryTick((value) => value + 1);
  }, []);

  const undo = useCallback(() => {
    if (history.current.index > 0) applyHistory(history.current.index - 1);
  }, [applyHistory]);

  const redo = useCallback(() => {
    if (history.current.index < history.current.stack.length - 1) {
      applyHistory(history.current.index + 1);
    }
  }, [applyHistory]);

  useEffect(() => {
    function onKey(event: KeyboardEvent) {
      const target = document.activeElement;
      const typing =
        Boolean(target) && ["INPUT", "TEXTAREA"].includes(target!.tagName);
      const meta = event.metaKey || event.ctrlKey;
      if (event.key === "Escape" && clipMenu) {
        event.preventDefault();
        setClipMenu(null);
        return;
      }
      if (meta && !typing && event.key.toLowerCase() === "z") {
        event.preventDefault();
        if (event.shiftKey) redo();
        else undo();
        return;
      }
      if (meta && !typing && event.key.toLowerCase() === "y") {
        event.preventDefault();
        redo();
        return;
      }
      if (event.code === "Space") {
        if (target && ["INPUT", "TEXTAREA", "BUTTON"].includes(target.tagName)) {
          return;
        }
        event.preventDefault();
        if (transport.current.playing) pause();
        else void start();
        return;
      }
      if (event.key !== "Delete" && event.key !== "Backspace") return;
      if (!selectedClip) return;
      if (typing) return;
      event.preventDefault();
      // Removing from the timeline is a `state` change, not a library delete:
      // the song stays in the user's Suno library.
      removeClip(selectedClip);
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [selectedClip, tracks, projectId, pause, start, removeClip, undo, redo, clipMenu]);

  // Library dock data: liked flags for the Liked tab.
  useEffect(() => {
    if (!libraryOpen) return;
    let active = true;
    fetchWebMusicLikedKeys()
      .then((keys) => {
        if (active) setLikedKeys(keys);
      })
      .catch(() => null);
    return () => {
      active = false;
    };
  }, [libraryOpen]);

  const readySongs = useMemo(
    () => songs.filter((song) => String(song.status).toUpperCase() === "SUCCESS"),
    [songs]
  );

  const likedSongs = useMemo(
    () =>
      readySongs.filter((song) =>
        (song.clips ?? []).some((clip) =>
          likedKeys.includes(clipTrackKey(song.id, clip.variant))
        )
      ),
    [readySongs, likedKeys]
  );

  /** Queue a full-project export and open the audio once Suno finishes. */
  async function exportProject() {
    if (!projectId || exporting) return;
    setExporting(true);
    setError("");
    setExportStatus("Preparing export…");
    try {
      const { clip_id: clipId } = await exportStudioSession(projectId);
      if (!clipId) throw new Error("Suno did not return an export clip");
      setExportStatus("Rendering…");
      for (let attempt = 0; attempt < 120; attempt += 1) {
        await new Promise((resolve) => window.setTimeout(resolve, 3000));
        const download = await getStudioClipDownload(clipId);
        if (download.download_url) {
          setExportStatus("");
          window.open(download.download_url, "_blank", "noopener");
          return;
        }
        if (download.ok === false) {
          throw new Error(
            download.message ||
              "Suno did not allow this download for the connected account."
          );
        }
        const clip = await getStudioClip(clipId);
        if (clip.status && ["error", "failed", "cancelled"].includes(clip.status)) {
          throw new Error("Suno could not render this export");
        }
      }
      throw new Error("Export is still running. Try again in a minute.");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Export failed");
    } finally {
      setExportStatus("");
      setExporting(false);
    }
  }

  function addTrack(name = "Audio Track") {
    const uid = newUid();
    const track: Track = {
      id: uid,
      remoteId: uid,
      name,
      color: COLORS[tracks.length % COLORS.length],
      clips: [],
      muted: false,
      solo: false,
      volume: 100,
    };
    setTracks((current) => [...current, track]);
    setSelectedTrack(track.id);
  }

  /** Append a clip to a lane at the playhead and persist it on Suno. */
  async function placeSong(song: WebMusicGeneration, trackId: string) {
    setBusy(true);
    setError("");
    try {
      const variant = chosenVariant(song);
      // The timeline lives in the project `state`, so adding a clip only needs
      // the project id and the clip's provider id — Suno's project clip list is
      // not involved (that endpoint is for project/workspace membership).
      const targetProject =
        projectId ?? (await createStudioSession(projectName)).id;
      if (!projectId) setProjectId(targetProject);
      // A project created for this clip has never been read back: fetch its
      // state so autosave has a real document to merge into.
      if (!baseStateRef.current) {
        await getStudioSession(targetProject)
          .then((doc) => {
            const state = asRecord(doc.state) ?? createDefaultState();
            baseStateRef.current = state;
            versionRef.current =
              typeof doc.latest_version_id === "string"
                ? doc.latest_version_id
                : null;
            setBps(readBps(state));
            if (typeof state.amplitude === "number") {
              setMasterVolume(
                Math.round(Math.min(1, Math.max(0, state.amplitude)) * 100)
              );
            }
          })
          .catch(() => null);
      }
      const providerClipId = await resolveStudioClipId(song.id, variant).catch(
        () => null
      );
      const duration =
        song.clips?.find((item) => item.variant === variant)?.duration_seconds ??
        null;
      const startBeats = Math.min(
        TIMELINE_BEATS - 1,
        Math.max(0, Math.round(currentPosition() * bpsRef.current))
      );
      setTracks((current) =>
        current.map((track) =>
          track.id === trackId
            ? {
                ...track,
                knownProviderIds: providerClipId
                  ? [...(track.knownProviderIds ?? []), providerClipId]
                  : track.knownProviderIds,
                clips: [
                  ...track.clips,
                  {
                    uid: newUid(),
                    songId: song.id,
                    variant,
                    providerClipId: providerClipId ?? undefined,
                    startBeats,
                    lengthBeats:
                      duration && duration > 0
                        ? Math.round(duration * bpsRef.current)
                        : undefined,
                  },
                ],
              }
            : track
        )
      );
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Could not open this song");
    } finally {
      setBusy(false);
    }
  }

  async function addSongToTimeline(song: WebMusicGeneration) {
    const target = tracks.find((track) => track.id === selectedTrack) ?? tracks[0];
    if (!target) {
      const uid = newUid();
      const track: Track = {
        id: uid,
        remoteId: uid,
        name: "Audio Track",
        color: COLORS[0],
        clips: [],
        muted: false,
        solo: false,
        volume: 100,
      };
      setTracks((current) => [...current, track]);
      setSelectedTrack(track.id);
      await placeSong(song, track.id);
      return;
    }
    await placeSong(song, target.id);
  }

  const timelineSeconds = TIMELINE_BEATS / bps;

  return (
    <div className="stv">
      <div ref={audioHostRef} hidden aria-hidden="true" />
      <header className="stv-top">
        <span className="st-chrome-project">{projectName}</span>
        <span className="st-chrome-dots">···</span>
        <span style={{ flex: 1 }} />
        <div className="stv-transport">
          <button
            type="button"
            className="stv-icon"
            aria-label="Undo"
            disabled={!canUndo}
            onClick={undo}
          >
            <Icon name="fa-rotate-left" />
          </button>
          <button
            type="button"
            className="stv-icon"
            aria-label="Redo"
            disabled={!canRedo}
            onClick={redo}
          >
            <Icon name="fa-rotate-right" />
          </button>
          <button
            type="button"
            className="stv-icon"
            aria-label="Go to start"
            onClick={() => seek(0)}
          >
            <Icon name="fa-backward-step" />
          </button>
          <button
            type="button"
            className="stv-icon"
            aria-label={playing ? "Pause" : "Play"}
            onClick={() => {
              if (transport.current.playing) pause();
              else void start();
            }}
          >
            <Icon name={playing ? "fa-pause" : "fa-play"} />
          </button>
          <button
            type="button"
            className={`stv-icon${metronome ? " on" : ""}`}
            aria-label="Metronome"
            aria-pressed={metronome}
            onClick={() => {
              lastClickBeatRef.current = -1;
              setMetronome((value) => !value);
            }}
          >
            <Icon name="fa-hourglass-half" />
          </button>
          <span className="stv-clock" ref={clockRef}>
            {clock(position)}
          </span>
          <span className="stv-bars" ref={barRef}>
            001.1.1
          </span>
        </div>
        <span style={{ flex: 1 }} />
        <span className="stv-bpm">{Math.round(bps * 60)} BPM</span>
        <span className="stv-sig">4/4</span>
        <button
          type="button"
          className="s-btn s-btn-ghost"
          disabled={!tracks.length || exporting}
          onClick={() => void exportProject()}
        >
          <Icon name="fa-arrow-up-from-bracket" />
          {exporting ? " Exporting…" : " Export"}
        </button>
        <button
          type="button"
          className="s-btn s-btn-ghost"
          onClick={() => setLibraryOpen((value) => !value)}
        >
          <Icon name="fa-folder-open" /> Library
        </button>
      </header>

      <div className="stv-body">
        <aside className="stv-tracks">
          {tracks.map((track, index) => (
            <div
              key={track.id}
              className={`stv-track${selectedTrack === track.id ? " on" : ""}`}
              onClick={() => setSelectedTrack(track.id)}
            >
              <div className="stv-track-top">
                <span className="stv-track-num">{index + 1}</span>
                <b>{track.name}</b>
                <span style={{ flex: 1 }} />
                <button
                  type="button"
                  className={`stv-pill${track.solo ? " on" : ""}`}
                  aria-pressed={track.solo}
                  aria-label={`Solo ${track.name}`}
                  onClick={(event) => {
                    event.stopPropagation();
                    setTracks((current) =>
                      current.map((item) =>
                        item.id === track.id ? { ...item, solo: !item.solo } : item
                      )
                    );
                  }}
                >
                  S
                </button>
                <button
                  type="button"
                  className={`stv-pill${track.muted ? " on" : ""}`}
                  aria-pressed={track.muted}
                  aria-label={`Mute ${track.name}`}
                  onClick={(event) => {
                    event.stopPropagation();
                    setTracks((current) =>
                      current.map((item) =>
                        item.id === track.id ? { ...item, muted: !item.muted } : item
                      )
                    );
                  }}
                >
                  M
                </button>
                <button type="button" className="stv-pill" aria-label="Record arm">
                  <Icon name="fa-circle" />
                </button>
              </div>
              <div className="stv-fader">
                <input
                  type="range"
                  min={0}
                  max={100}
                  value={track.volume}
                  aria-label={`${track.name} volume`}
                  aria-valuetext={`${track.volume}%`}
                  onChange={(event) =>
                    setTracks((current) =>
                      current.map((item) =>
                        item.id === track.id
                          ? { ...item, volume: Number(event.target.value) }
                          : item
                      )
                    )
                  }
                />
                <span className="stv-track-fx"><Icon name="fa-sliders" /></span>
              </div>
            </div>
          ))}
          <button type="button" className="stv-add-track" onClick={() => addTrack()}>
            <Icon name="fa-plus" /> Add new track
          </button>
        </aside>

        <main className="stv-canvas">
          <div
            className="stv-ruler"
            onPointerDown={(event) => {
              const rect = event.currentTarget.getBoundingClientRect();
              if (!rect.width) return;
              const ratio = (event.clientX - rect.left) / rect.width;
              seek(Math.max(0, Math.min(1, ratio)) * timelineSeconds);
            }}
          >
            {Array.from({ length: BARS }).map((_, index) => (
              <span key={index} style={{ width: `${100 / BARS}%` }}>
                {index + 1}
              </span>
            ))}
          </div>
          <div className="stv-grid" style={{ width: `${Math.round(zoom * 100)}%` }}>
            {Array.from({ length: BARS }).map((_, index) => (
              <span key={index} style={{ left: `${(index / BARS) * 100}%` }} />
            ))}
            {tracks.map((track, index) => (
              <div
                className="stv-lane"
                key={track.id}
                style={{ top: index * 58 }}
                onDragOver={(event) => event.preventDefault()}
                onPointerDown={(event) => {
                  // Empty-lane click seeks; clip pointer downs handle themselves.
                  if (event.target !== event.currentTarget) return;
                  const rect = event.currentTarget.getBoundingClientRect();
                  if (!rect.width) return;
                  const ratio = (event.clientX - rect.left) / rect.width;
                  seek(Math.max(0, Math.min(1, ratio)) * timelineSeconds);
                }}
                onPointerMove={(event) => {
                  const fade = fadeRef.current;
                  if (fade) {
                    const delta =
                      ((event.clientX - fade.startX) /
                        Math.max(1, fade.laneWidth)) *
                      TIMELINE_BEATS;
                    const next = Math.min(
                      fade.lengthBeats,
                      Math.max(
                        0,
                        fade.fadeBeats + (fade.edge === "in" ? delta : -delta)
                      )
                    );
                    updateClip(
                      fade.uid,
                      fade.edge === "in"
                        ? { fadeInBeats: Math.round(next) }
                        : { fadeOutBeats: Math.round(next) }
                    );
                    return;
                  }
                  const trim = trimRef.current;
                  if (trim) {
                    const delta =
                      ((event.clientX - trim.startX) /
                        Math.max(1, trim.laneWidth)) *
                      TIMELINE_BEATS;
                    if (trim.edge === "start") {
                      const minStart = Math.max(
                        0,
                        trim.startBeats - trim.readStartBeats
                      );
                      const maxStart = trim.startBeats + trim.lengthBeats - 1;
                      const next = Math.min(
                        maxStart,
                        Math.max(minStart, trim.startBeats + delta)
                      );
                      const shift = next - trim.startBeats;
                      updateClip(trim.uid, {
                        startBeats: Math.round(next),
                        lengthBeats: Math.round(trim.lengthBeats - shift),
                        readStartBeats: Math.round(
                          Math.max(0, trim.readStartBeats + shift)
                        ),
                      });
                    } else {
                      const next = Math.max(
                        1,
                        Math.min(
                          TIMELINE_BEATS - trim.startBeats,
                          trim.lengthBeats + delta
                        )
                      );
                      updateClip(trim.uid, { lengthBeats: Math.round(next) });
                    }
                    return;
                  }
                  const drag = dragRef.current;
                  if (!drag) return;
                  const delta =
                    ((event.clientX - drag.startX) / Math.max(1, drag.laneWidth)) *
                    TIMELINE_BEATS;
                  const next = Math.min(
                    TIMELINE_BEATS - 1,
                    Math.max(0, drag.startBeat + delta)
                  );
                  updateClip(drag.uid, { startBeats: Math.round(next) });
                }}
                onPointerUp={() => {
                  endDrag();
                }}
                onPointerLeave={() => {
                  endDrag();
                }}
                onDrop={(event) => {
                  event.preventDefault();
                  const songId = event.dataTransfer.getData("text/song");
                  const song = songsById.get(songId);
                  if (song) void placeSong(song, track.id);
                }}
              >
                {track.clips.map((clip) => {
                  const song = songsById.get(clip.songId);
                  const place = placed.get(clip.uid);
                  const startPct = (clip.startBeats / TIMELINE_BEATS) * 100;
                  const widthPct = place
                    ? Math.min(
                        100 - startPct,
                        (place.duration / timelineSeconds) * 100
                      )
                    : 16;
                  const lengthBeats = Math.max(1, clip.lengthBeats ?? 8);
                  const fadeInPct = Math.min(
                    100,
                    ((clip.fadeInBeats ?? 0) / lengthBeats) * 100
                  );
                  const fadeOutPct = Math.min(
                    100 - fadeInPct,
                    ((clip.fadeOutBeats ?? 0) / lengthBeats) * 100
                  );
                  return (
                    <span
                      key={clip.uid}
                      className={`stv-clip${selectedClip === clip.uid ? " on" : ""}`}
                      onClick={() => {
                        setSelectedClip(clip.uid);
                        setSelectedTrack(track.id);
                      }}
                      onPointerDown={(event) => {
                        const lane = (event.currentTarget as HTMLElement)
                          .parentElement;
                        dragRef.current = {
                          uid: clip.uid,
                          startX: event.clientX,
                          startBeat: clip.startBeats,
                          laneWidth: lane?.clientWidth || 1,
                        };
                      }}
                      onContextMenu={(event) => {
                        event.preventDefault();
                        setSelectedClip(clip.uid);
                        setClipMenu({
                          uid: clip.uid,
                          x: event.clientX,
                          y: event.clientY,
                        });
                      }}
                      style={{
                        left: `${startPct}%`,
                        width: `${Math.max(4, widthPct)}%`,
                        background: `linear-gradient(90deg, ${track.color}dd, ${track.color}77)`,
                      }}
                    >
                      <span
                        className="stv-clip-handle start"
                        aria-hidden="true"
                        onPointerDown={(event) => {
                          event.stopPropagation();
                          const lane = (event.currentTarget.parentElement
                            ?.parentElement ?? null) as HTMLElement | null;
                          trimRef.current = {
                            uid: clip.uid,
                            edge: "start",
                            startX: event.clientX,
                            startBeats: clip.startBeats,
                            lengthBeats: Math.max(1, clip.lengthBeats ?? 8),
                            readStartBeats: Math.max(0, clip.readStartBeats ?? 0),
                            laneWidth: lane?.clientWidth || 1,
                          };
                        }}
                      />
                      <span className="stv-clip-label">
                        {song?.title || "Clip"}
                      </span>
                      {fadeInPct > 0 ? (
                        <span
                          className="stv-clip-fade in"
                          style={{ width: `${fadeInPct}%` }}
                        />
                      ) : null}
                      {fadeOutPct > 0 ? (
                        <span
                          className="stv-clip-fade out"
                          style={{ width: `${fadeOutPct}%` }}
                        />
                      ) : null}
                      {selectedClip === clip.uid ? (
                        <>
                          <span
                            className="stv-clip-fade-handle in"
                            aria-hidden="true"
                            style={{ left: `${fadeInPct}%` }}
                            title="Fade in"
                            onPointerDown={(event) => {
                              event.stopPropagation();
                              const lane = (event.currentTarget.parentElement
                                ?.parentElement ?? null) as HTMLElement | null;
                              fadeRef.current = {
                                uid: clip.uid,
                                edge: "in",
                                startX: event.clientX,
                                fadeBeats: clip.fadeInBeats ?? 0,
                                lengthBeats,
                                laneWidth: lane?.clientWidth || 1,
                              };
                            }}
                          />
                          <span
                            className="stv-clip-fade-handle out"
                            aria-hidden="true"
                            style={{ right: `${fadeOutPct}%` }}
                            title="Fade out"
                            onPointerDown={(event) => {
                              event.stopPropagation();
                              const lane = (event.currentTarget.parentElement
                                ?.parentElement ?? null) as HTMLElement | null;
                              fadeRef.current = {
                                uid: clip.uid,
                                edge: "out",
                                startX: event.clientX,
                                fadeBeats: clip.fadeOutBeats ?? 0,
                                lengthBeats,
                                laneWidth: lane?.clientWidth || 1,
                              };
                            }}
                          />
                        </>
                      ) : null}
                      <span
                        className="stv-clip-handle end"
                        aria-hidden="true"
                        onPointerDown={(event) => {
                          event.stopPropagation();
                          const lane = (event.currentTarget.parentElement
                            ?.parentElement ?? null) as HTMLElement | null;
                          trimRef.current = {
                            uid: clip.uid,
                            edge: "end",
                            startX: event.clientX,
                            startBeats: clip.startBeats,
                            lengthBeats: Math.max(1, clip.lengthBeats ?? 8),
                            readStartBeats: Math.max(0, clip.readStartBeats ?? 0),
                            laneWidth: lane?.clientWidth || 1,
                          };
                        }}
                      />
                    </span>
                  );
                })}
              </div>
            ))}
            <div
              className="stv-playhead"
              ref={playheadRef}
              style={{ left: `${(position / timelineSeconds) * 100}%` }}
            />
            {!tracks.length ? (
              <div className="stv-empty">
                <Icon name="fa-music" />
                <b>Add a track, then drop a song on it</b>
                <p className="s-note">Use “Add new track” on the left, then Library.</p>
              </div>
            ) : null}
          </div>
        </main>

        {libraryOpen ? (
          <aside className="stv-library">
            <div className="stv-library-head">
              <b>Library</b>
              <button
                type="button"
                className="stv-icon"
                aria-label="Close library"
                onClick={() => setLibraryOpen(false)}
              >
                <Icon name="fa-xmark" />
              </button>
            </div>
            <div className="stv-library-tabs" role="tablist">
              {(
                [
                  ["songs", "Songs"],
                  ["liked", "Liked"],
                ] as const
              ).map(([key, label]) => (
                <button
                  key={key}
                  type="button"
                  role="tab"
                  aria-selected={libraryTab === key}
                  className={`stv-library-tab${libraryTab === key ? " on" : ""}`}
                  onClick={() => setLibraryTab(key)}
                >
                  {label}
                </button>
              ))}
            </div>
            <div className="stv-library-list">
              {(libraryTab === "liked" ? likedSongs : readySongs).length ? (
                (libraryTab === "liked" ? likedSongs : readySongs).map((song) => (
                  <button
                    key={song.id}
                    type="button"
                    className="stv-library-row"
                    draggable
                    onDragStart={(event) => {
                      event.dataTransfer.setData("text/song", song.id);
                      event.dataTransfer.effectAllowed = "copy";
                    }}
                    disabled={busy}
                    onClick={() => void addSongToTimeline(song)}
                  >
                    <span
                      className="stv-art"
                      style={
                        song.clips?.[0]?.image_url
                          ? { backgroundImage: `url(${song.clips[0].image_url})` }
                          : undefined
                      }
                    />
                    <span className="stv-library-body">
                      <b>{song.title}</b>
                      <small>{song.style || "—"}</small>
                    </span>
                    <Icon name="fa-plus" />
                  </button>
                ))
              ) : (
                <p className="s-note">
                  {libraryTab === "liked"
                    ? "No liked songs yet."
                    : "No finished songs yet."}
                </p>
              )}
            </div>
          </aside>
        ) : null}
      </div>

      <footer className="stv-bottom">
        <div className="stv-master">
          <span className="stv-master-label">Main</span>
          <input
            type="range"
            min={0}
            max={100}
            value={masterVolume}
            aria-label="Master volume"
            aria-valuetext={`${masterVolume}%`}
            onChange={(event) => setMasterVolume(Number(event.target.value))}
          />
          <Icon name="fa-volume-high" />
        </div>
        <div className="stv-prompt">
          <button type="button" className="stv-icon" aria-label="Add">
            <Icon name="fa-plus" />
          </button>
          <input
            value={prompt}
            onChange={(event) => setPrompt(event.target.value)}
            placeholder="Select a spot on the timeline and ask me to add a part"
            aria-label="Ask Studio to add a part"
          />
          <span className="stv-model">V6</span>
          <button
            type="button"
            className="stv-icon"
            aria-label="Send"
            disabled={!prompt.trim()}
            onClick={() => setPrompt("")}
          >
            <Icon name="fa-arrow-up" />
          </button>
        </div>
        <div className="stv-tools">
          <span className="s-note">Zoom</span>
          <input
            type="range"
            min={0.5}
            max={2}
            step={0.1}
            value={zoom}
            aria-label="Zoom"
            onChange={(event) => setZoom(Number(event.target.value))}
          />
          {hydrating ? <span className="s-note">Loading…</span> : null}
          {saving ? <span className="s-note">Saving…</span> : null}
          {saveStatus === "conflict" ? (
            <span className="s-note">Reconciling…</span>
          ) : null}
          {busy ? <span className="s-note">Opening…</span> : null}
          {exportStatus ? <span className="s-note">{exportStatus}</span> : null}
          {playbackIssue ? (
            <span
              className="s-note"
              title="Suno returns 422 encrypted_playback_required for clips with a packaged master."
            >
              Some clips can&apos;t play in the browser yet
            </span>
          ) : null}
          {error ? <span className="s-error">{error}</span> : null}
        </div>
      </footer>

      {clipMenu ? (
        <div
          className="stv-menu-backdrop"
          onClick={() => setClipMenu(null)}
          onContextMenu={(event) => {
            event.preventDefault();
            setClipMenu(null);
          }}
        >
          <div
            className="stv-menu"
            role="menu"
            style={{ left: clipMenu.x, top: clipMenu.y }}
            onClick={(event) => event.stopPropagation()}
          >
            <button
              type="button"
              role="menuitem"
              onClick={() => {
                duplicateClip(clipMenu.uid);
                setClipMenu(null);
              }}
            >
              Duplicate
            </button>
            <button
              type="button"
              role="menuitem"
              title="Move the playhead inside the clip first"
              onClick={() => {
                splitClip(clipMenu.uid);
                setClipMenu(null);
              }}
            >
              Split at playhead
            </button>
            <button
              type="button"
              role="menuitem"
              onClick={() => removeClip(clipMenu.uid)}
            >
              Delete
            </button>
          </div>
        </div>
      ) : null}
    </div>
  );
}
