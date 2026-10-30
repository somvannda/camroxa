"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useSearchParams } from "next/navigation";

import { Icon } from "@/components/Icon";
import type { WebMusicGeneration } from "@/lib/library-api";
import {
  StudioSaveConflictError,
  WebMusicApiError,
  getStudioSession,
  listWebMusicGenerations,
  resolveStudioClips,
  saveStudioSession,
  studioSessionForClip,
  updateStudioSessionClips,
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
  duration: number;
  src: string;
};

type MixerEngine = {
  ctx: AudioContext;
  master: GainNode;
  tracks: Map<string, GainNode>;
  sources: Map<string, MediaElementAudioSourceNode>;
};

type SaveStatus = "idle" | "saving" | "saved" | "error" | "conflict";

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
    readStartBeats: 0,
    fadeInBeats: 0,
    fadeOutBeats: 0,
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
}): Record<string, unknown> | null {
  const baseTracks = Array.isArray(input.base.tracks)
    ? (input.base.tracks as unknown[])
        .map(asRecord)
        .filter((track): track is Record<string, unknown> => Boolean(track))
    : [];
  const baseAudio = baseTracks.filter((track) => track.type === "audio");
  const template = baseAudio[0] ?? null;
  const byId = new Map(baseTracks.map((track) => [String(track.id ?? ""), track]));
  const claimed = new Set<string>();
  const out: Record<string, unknown>[] = [];

  for (const [index, track] of input.tracks.entries()) {
    // Match by id first, then by position, then fall back to the template so a
    // new lane still inherits Suno's unknown per-track fields.
    let source = (track.remoteId && byId.get(track.remoteId)) || null;
    if (!source) {
      const candidate = baseAudio[index];
      if (candidate && !claimed.has(String(candidate.id ?? ""))) source = candidate;
    }
    if (!source) source = template;
    if (!source) return null;
    const sourceId = String(source.id ?? "");
    const sourceAlreadyClaimed = claimed.has(sourceId);
    const reusesTemplate = sourceAlreadyClaimed && source === template;
    claimed.add(sourceId);

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
    const kept = reusesTemplate
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

  return { ...input.base, amplitude: input.masterVolume / 100, tracks: out };
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
  const dragRef = useRef<{
    uid: string;
    startX: number;
    startBeat: number;
    laneWidth: number;
  } | null>(null);
  const [projectName, setProjectName] = useState("Untitled Project");
  const [projectId, setProjectId] = useState<string | null>(projectParam);
  const [libraryOpen, setLibraryOpen] = useState(false);
  const [playing, setPlaying] = useState(false);
  const [position, setPosition] = useState(0);
  const [zoom, setZoom] = useState(1);
  const [masterVolume, setMasterVolume] = useState(80);
  const [bps, setBps] = useState(DEFAULT_BPS);
  const [hydrating, setHydrating] = useState(Boolean(projectParam));
  const [saving, setSaving] = useState(false);
  const [saveStatus, setSaveStatus] = useState<SaveStatus>("idle");
  const [prompt, setPrompt] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
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
          duration,
          src,
        });
      });
    });
    return map;
  }, [tracks, songsById, measured, bps]);

  /** Everything the imperative transport loop needs, kept current each render. */
  const live = useRef({ tracks, placed, masterVolume, bps });
  live.current = { tracks, placed, masterVolume, bps };

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
    getStudioSession(projectParam)
      .then(async (session) => {
        if (!active) return;
        const title = typeof session.title === "string" ? session.title : null;
        if (title) setProjectName(title);
        const doc = asRecord(session.state);
        if (!doc) return;
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
            : 80;
        setMasterVolume(nextMaster);

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
                : 80,
          });
        });
        if (nextTracks.length) setTracks(nextTracks);
        // Baseline exactly what we just loaded so hydration never autosaves.
        savedSnapshotRef.current = JSON.stringify({
          tracks: nextTracks.length ? nextTracks : tracks,
          masterVolume: nextMaster,
          projectName: title ?? "Untitled Project",
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
          el.currentTime = seconds - (clip?.start ?? 0);
        } catch {
          /* metadata not ready yet: the next entry retries */
        }
        void el.play().catch(() => undefined);
      });
      windowRef.current = insideNow;
    },
    []
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
        source.connect(trackGain(engine, trackId));
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
    engineRef.current = { ctx, master, tracks: new Map(), sources: new Map() };
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
    const step = () => {
      const running = engineRef.current;
      if (!running || !transport.current.playing) return;
      const seconds = currentPosition();
      updateView(seconds);
      syncClips(seconds, true, false);
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
    stopLoop,
    syncClips,
    updateView,
  ]);

  /** A clip was dropped at a new spot: re-arm it if the transport is running. */
  const endDrag = useCallback(() => {
    const dragging = dragRef.current;
    dragRef.current = null;
    if (dragging && transport.current.playing) {
      syncClips(currentPosition(), true, true);
    }
  }, [currentPosition, syncClips]);

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
    const snapshot = JSON.stringify({ tracks, masterVolume, projectName });
    if (snapshot === savedSnapshotRef.current) return;
    const timer = window.setTimeout(() => void saveNowRef.current(), 3000);
    return () => window.clearTimeout(timer);
  }, [tracks, masterVolume, projectName, projectId, hydrating]);

  useEffect(() => {
    function onKey(event: KeyboardEvent) {
      if (event.code === "Space") {
        const target = document.activeElement;
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
      const target = document.activeElement;
      if (target && ["INPUT", "TEXTAREA"].includes(target.tagName)) return;
      event.preventDefault();
      const owner = tracks.find((track) =>
        track.clips.some((clip) => clip.uid === selectedClip)
      );
      const clip = owner?.clips.find((item) => item.uid === selectedClip);
      if (clip && projectId) {
        void updateStudioSessionClips(
          projectId,
          [clip.songId],
          [clip.variant],
          true
        ).catch(() => null);
      }
      setTracks((current) =>
        current.map((track) => ({
          ...track,
          clips: track.clips.filter((item) => item.uid !== selectedClip),
        }))
      );
      setSelectedClip(null);
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [selectedClip, tracks, projectId, pause, start]);

  const readySongs = useMemo(
    () => songs.filter((song) => String(song.status).toUpperCase() === "SUCCESS"),
    [songs]
  );

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
      volume: 80,
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
      const session = await studioSessionForClip(song.id, variant);
      if (!projectId) setProjectId(session.project_id);
      const result = await updateStudioSessionClips(
        session.project_id,
        [song.id],
        [variant]
      ).catch(() => null);
      // A project created for this clip has never been read back: fetch its
      // state so autosave has a real document to merge into.
      if (!baseStateRef.current) {
        await getStudioSession(session.project_id)
          .then((doc) => {
            const state = asRecord(doc.state);
            if (!state) return;
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
                knownProviderIds: result?.clip_ids?.[0]
                  ? [...(track.knownProviderIds ?? []), result.clip_ids[0]]
                  : track.knownProviderIds,
                clips: [
                  ...track.clips,
                  {
                    uid: newUid(),
                    songId: song.id,
                    variant,
                    providerClipId: result?.clip_ids?.[0],
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
        volume: 80,
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
          <button type="button" className="stv-icon" aria-label="Metronome">
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
        <button type="button" className="s-btn s-btn-ghost" disabled={!tracks.length}>
          <Icon name="fa-arrow-up-from-bracket" /> Export
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
          <div className="stv-ruler">
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
                onPointerMove={(event) => {
                  const drag = dragRef.current;
                  if (!drag) return;
                  const delta =
                    ((event.clientX - drag.startX) / Math.max(1, drag.laneWidth)) *
                    TIMELINE_BEATS;
                  const next = Math.min(
                    TIMELINE_BEATS - 1,
                    Math.max(0, drag.startBeat + delta)
                  );
                  setTracks((current) =>
                    current.map((item) =>
                      item.id === track.id
                        ? {
                            ...item,
                            clips: item.clips.map((clip) =>
                              clip.uid === drag.uid
                                ? { ...clip, startBeats: Math.round(next) }
                                : clip
                            ),
                          }
                        : item
                    )
                  );
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
                      style={{
                        left: `${startPct}%`,
                        width: `${Math.max(4, widthPct)}%`,
                        background: `linear-gradient(90deg, ${track.color}dd, ${track.color}77)`,
                      }}
                    >
                      {song?.title || "Clip"}
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
            <div className="stv-library-list">
              {readySongs.length ? (
                readySongs.map((song) => (
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
                <p className="s-note">No finished songs yet.</p>
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
          {error ? <span className="s-error">{error}</span> : null}
        </div>
      </footer>
    </div>
  );
}
