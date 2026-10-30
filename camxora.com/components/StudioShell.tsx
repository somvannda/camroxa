"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useSearchParams } from "next/navigation";

import { Icon } from "@/components/Icon";
import type { WebMusicGeneration } from "@/lib/library-api";
import {
  getStudioSession,
  listWebMusicGenerations,
  studioSessionForClip,
  updateStudioSessionClips,
} from "@/lib/web-music-api";

const BARS = 24;
/** Ruler bars have always run at 1.25 s in the project view (24 bars = 30 s). */
const SECONDS_PER_BAR = 1.25;
const TIMELINE_SECONDS = BARS * SECONDS_PER_BAR;
const COLORS = ["#7466F1", "#A259FF", "#2f7bf6", "#25d366", "#f59e0b"];

type ClipRef = { uid: string; songId: string; variant: "ok" | "alt" };

type Track = {
  id: string;
  name: string;
  color: string;
  clips: ClipRef[];
  muted: boolean;
  solo: boolean;
  volume: number;
};

type PlacedClip = ClipRef & {
  trackId: string;
  /** Seconds from the start of the (browser-local) timeline. */
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

function clock(seconds: number) {
  const m = Math.floor(seconds / 60);
  const s = Math.floor(seconds % 60);
  const ms = Math.floor((seconds % 1) * 1000);
  return `${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}.${String(ms).padStart(3, "0")}`;
}

function newClipUid() {
  if (typeof crypto !== "undefined" && typeof crypto.randomUUID === "function") {
    return crypto.randomUUID();
  }
  return `clip-${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

function chosenVariant(song?: WebMusicGeneration): "ok" | "alt" {
  const clip = song?.clips?.find((item) => item.ready) ?? song?.clips?.[0];
  return clip?.variant === "alt" ? "alt" : "ok";
}

/**
 * Suno's project view: track panel on the left, bar-numbered timeline in the
 * middle, prompt bar along the bottom, transport in the header.
 *
 * Playback is a real mixer: one stream per placed clip, each routed through its
 * track's gain into the master strip, so volume / mute / solo / Main all change
 * what you hear. The arrangement itself is still browser-local — Suno's `state`
 * document has not been captured yet, so nothing here is written back as audio
 * positions.
 */
export function StudioShell() {
  const params = useSearchParams();
  const projectParam = params.get("project");

  const [songs, setSongs] = useState<WebMusicGeneration[]>([]);
  const [tracks, setTracks] = useState<Track[]>([]);
  const [selectedTrack, setSelectedTrack] = useState<string | null>(null);
  const [selectedClip, setSelectedClip] = useState<string | null>(null);
  const [offsets, setOffsets] = useState<Record<string, number>>({});
  const dragRef = useRef<{
    uid: string;
    startX: number;
    startLeft: number;
    laneWidth: number;
  } | null>(null);
  const [projectName, setProjectName] = useState("Untitled Project");
  const [projectId, setProjectId] = useState<string | null>(projectParam);
  const [libraryOpen, setLibraryOpen] = useState(false);
  const [playing, setPlaying] = useState(false);
  const [position, setPosition] = useState(0);
  const [zoom, setZoom] = useState(1);
  const [masterVolume, setMasterVolume] = useState(80);
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

  const songsById = useMemo(
    () => new Map(songs.map((song) => [song.id, song])),
    [songs]
  );

  const placed = useMemo(() => {
    const map = new Map<string, PlacedClip>();
    tracks.forEach((track) => {
      track.clips.forEach((clip, clipIndex) => {
        const song = songsById.get(clip.songId);
        const startPct = offsets[clip.uid] ?? clipIndex * 18;
        const start = Math.min(
          TIMELINE_SECONDS - 1,
          (startPct / 100) * TIMELINE_SECONDS
        );
        const key = `${clip.songId}:${clip.variant}`;
        const declared = song?.clips?.find((item) => item.variant === clip.variant)
          ?.duration_seconds;
        const known = measured[key] ?? declared ?? null;
        // Unknown length: let the stream run to the end of the timeline rather
        // than cut audio we cannot measure yet.
        const duration =
          known && known > 0
            ? Math.min(known, TIMELINE_SECONDS - start)
            : TIMELINE_SECONDS - start;
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
  }, [tracks, offsets, songsById, measured]);

  /** Everything the imperative transport loop needs, kept current each render. */
  const live = useRef({ tracks, placed, masterVolume });
  live.current = { tracks, placed, masterVolume };

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

  useEffect(() => {
    if (!projectParam) return;
    let active = true;
    setProjectId(projectParam);
    getStudioSession(projectParam)
      .then((session) => {
        if (!active) return;
        const title = (session as { title?: string }).title;
        if (title) setProjectName(title);
      })
      .catch(() => {
        /* older project or a signed-out pool: keep the id we have */
      });
    return () => {
      active = false;
    };
  }, [projectParam]);

  const currentPosition = useCallback(() => {
    const engine = engineRef.current;
    if (!engine || !transport.current.playing) return transport.current.at;
    return transport.current.at + (engine.ctx.currentTime - transport.current.from);
  }, []);

  const updateView = useCallback((seconds: number) => {
    if (clockRef.current) clockRef.current.textContent = clock(seconds);
    if (barRef.current) {
      const bar = Math.max(1, Math.floor(seconds / SECONDS_PER_BAR) + 1);
      barRef.current.textContent = `${String(bar).padStart(3, "0")}.1.1`;
    }
    if (playheadRef.current) {
      playheadRef.current.style.left = `${(seconds / TIMELINE_SECONDS) * 100}%`;
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
    (
      engine: MixerEngine,
      liveTracks: Track[],
      master: number
    ) => {
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
    const at = Math.min(TIMELINE_SECONDS, Math.max(0, currentPosition()));
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
    if (transport.current.at >= TIMELINE_SECONDS) transport.current.at = 0;
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
      if (seconds >= TIMELINE_SECONDS) {
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
      const next = Math.min(TIMELINE_SECONDS, Math.max(0, seconds));
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
    const track: Track = {
      id: `${Date.now()}-${tracks.length}`,
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

  /** Append a clip to a lane and persist the clip on the Suno project. */
  async function placeSong(song: WebMusicGeneration, trackId: string) {
    setBusy(true);
    setError("");
    try {
      const variant = chosenVariant(song);
      const session = await studioSessionForClip(song.id, variant);
      if (!projectId) setProjectId(session.project_id);
      // Persist on Suno's surface: the clip joins the Studio project.
      await updateStudioSessionClips(session.project_id, [song.id], [variant]).catch(
        () => null
      );
      setTracks((current) =>
        current.map((track) =>
          track.id === trackId
            ? {
                ...track,
                clips: [
                  ...track.clips,
                  { uid: newClipUid(), songId: song.id, variant },
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
      const track: Track = {
        id: `${Date.now()}-0`,
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
        <span className="stv-bpm">120 BPM</span>
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
                    ((event.clientX - drag.startX) / Math.max(1, drag.laneWidth)) * 100;
                  setOffsets((current) => ({
                    ...current,
                    [drag.uid]: Math.min(82, Math.max(0, drag.startLeft + delta)),
                  }));
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
                {track.clips.map((clip, clipIndex) => {
                  const song = songsById.get(clip.songId);
                  const startPct = offsets[clip.uid] ?? clipIndex * 18;
                  const place = placed.get(clip.uid);
                  const widthPct = place
                    ? Math.min(
                        100 - startPct,
                        (place.duration / TIMELINE_SECONDS) * 100
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
                          startLeft: startPct,
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
              style={{ left: `${(position / TIMELINE_SECONDS) * 100}%` }}
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
          {busy ? <span className="s-note">Opening…</span> : null}
          {error ? <span className="s-error">{error}</span> : null}
        </div>
      </footer>
    </div>
  );
}
