"use client";

import Link from "next/link";
import {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
  type CSSProperties,
  type PointerEvent as ReactPointerEvent,
} from "react";
import { Icon } from "@/components/Icon";
import { useAuth } from "@/components/AuthProvider";
import { usePlayer } from "@/components/PlayerProvider";
import { fetchGenerations, type WebMusicClip, type WebMusicGeneration } from "@/lib/library-api";
import { fetchWebMusicClipBlob } from "@/lib/web-music-api";

type Clip = {
  id: string;
  generationId: string;
  variant: string;
  title: string;
  style: string;
  color: string;
  image?: string | null;
  start: number;
  duration: number;
  offset: number;
  volume: number;
  pan: number;
  muted: boolean;
  solo: boolean;
};

type DragState = {
  id: string;
  mode: "move" | "left" | "right";
  startX: number;
  start: number;
  duration: number;
  offset: number;
  trackWidth: number;
};

type StoredSession = {
  name?: string;
  bpm?: number;
  zoom?: number;
  master?: number;
  lanes?: Clip[];
};

const COLORS = ["#8b5cf6", "#0ea5e9", "#22c55e", "#f59e0b", "#ec4899", "#14b8a6"];
const MIN_CLIP = 3;
const STORAGE_PREFIX = "camxora-studio-session-v1";

function clamp(value: number, min: number, max: number): number {
  return Math.min(max, Math.max(min, value));
}

function snap(value: number): number {
  return Math.round(value * 2) / 2;
}

function makeId(): string {
  if (typeof crypto !== "undefined" && "randomUUID" in crypto) return crypto.randomUUID();
  return `clip-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
}

function formatTime(seconds: number): string {
  const total = Math.max(0, Math.floor(seconds));
  return `${Math.floor(total / 60)}:${String(total % 60).padStart(2, "0")}`;
}

function clipFromGeneration(
  generation: WebMusicGeneration,
  index: number,
  start: number,
  variant?: string
): Clip | null {
  const clips = generation.clips ?? [];
  const clip: WebMusicClip | undefined =
    clips.find((item) => item.variant === variant) ??
    clips.find((item) => item.ready && item.audio_url) ??
    clips.find((item) => item.audio_url) ??
    clips[0];
  if (!clip && !generation.id) return null;
  return {
    id: makeId(),
    generationId: generation.id,
    variant: clip?.variant || "ok",
    title: clip?.title || generation.title || "Untitled",
    style: generation.style || generation.model_label || "Camxora",
    color: COLORS[index % COLORS.length],
    image: clip?.image_url || null,
    start,
    duration: Math.max(12, Math.round(clip?.duration_seconds || 180)),
    offset: 0,
    volume: 80,
    pan: 0,
    muted: false,
    solo: false,
  };
}

export function StudioEditorView() {
  const { user, loading: authLoading } = useAuth();
  const { playing: mainPlaying, togglePlay: toggleMainPlayer } = usePlayer();
  const [items, setItems] = useState<WebMusicGeneration[]>([]);
  const [lanes, setLanes] = useState<Clip[]>([]);
  const [selected, setSelected] = useState<string | null>(null);
  const [sessionName, setSessionName] = useState("Untitled session");
  const [bpm, setBpm] = useState(90);
  const [zoom, setZoom] = useState(1);
  const [master, setMaster] = useState(80);
  const [playhead, setPlayhead] = useState(0);
  const [playing, setPlaying] = useState(false);
  const [audioLoading, setAudioLoading] = useState(false);
  const [audioError, setAudioError] = useState("");
  const [loaded, setLoaded] = useState(false);
  const [savedAt, setSavedAt] = useState<Date | null>(null);
  const [history, setHistory] = useState<Clip[][]>([]);
  const [future, setFuture] = useState<Clip[][]>([]);
  const dragRef = useRef<DragState | null>(null);
  const playheadRef = useRef(0);
  const timelineDurationRef = useRef(180);
  const audioCtxRef = useRef<AudioContext | null>(null);
  const masterGainRef = useRef<GainNode | null>(null);
  const buffersRef = useRef<Map<string, AudioBuffer>>(new Map());
  const sourcesRef = useRef<AudioBufferSourceNode[]>([]);
  const nodesRef = useRef<Map<string, { gain: GainNode; panner: StereoPannerNode }>>(new Map());
  const startedAtRef = useRef(0);
  const startPlayheadRef = useRef(0);
  const rafRef = useRef<number | null>(null);

  const storageKey = user ? `${STORAGE_PREFIX}:${user.id}` : "";

  useEffect(() => {
    playheadRef.current = playhead;
  }, [playhead]);

  useEffect(() => {
    if (authLoading || !user) return;
    let active = true;
    setLoaded(false);
    fetchGenerations(100)
      .then((next) => {
        if (!active) return;
        setItems(next);
        const raw = storageKey ? window.localStorage.getItem(storageKey) : null;
        if (raw) {
          try {
            const saved = JSON.parse(raw) as StoredSession;
            const savedLanes = Array.isArray(saved.lanes)
              ? saved.lanes.filter(
                  (lane) =>
                    lane &&
                    typeof lane.id === "string" &&
                    typeof lane.generationId === "string" &&
                    Number.isFinite(lane.start) &&
                    Number.isFinite(lane.duration)
                )
              : [];
            setLanes(savedLanes);
            setSelected(savedLanes[0]?.id ?? null);
            if (saved.name) setSessionName(saved.name);
            if (Number.isFinite(saved.bpm)) setBpm(clamp(Number(saved.bpm), 40, 220));
            if (Number.isFinite(saved.zoom)) setZoom(clamp(Number(saved.zoom), 0.7, 2));
            if (Number.isFinite(saved.master)) setMaster(clamp(Number(saved.master), 0, 100));
          } catch {
            setLanes([]);
          }
        }
      })
      .catch(() => {
        if (active) setItems([]);
      })
      .finally(() => {
        if (active) setLoaded(true);
      });
    return () => {
      active = false;
    };
  }, [authLoading, user, storageKey]);

  useEffect(() => {
    if (!loaded || !user || !storageKey) return;
    const timer = window.setTimeout(() => {
      const payload: StoredSession = { name: sessionName, bpm, zoom, master, lanes };
      window.localStorage.setItem(storageKey, JSON.stringify(payload));
      setSavedAt(new Date());
    }, 350);
    return () => window.clearTimeout(timer);
  }, [loaded, user, storageKey, sessionName, bpm, zoom, master, lanes]);

  const timelineDuration = useMemo(() => {
    const end = lanes.reduce((max, lane) => Math.max(max, lane.start + lane.duration), 0);
    return Math.max(240, Math.ceil(Math.max(end, playhead + 10) / 30) * 30);
  }, [lanes, playhead]);

  useEffect(() => {
    timelineDurationRef.current = timelineDuration;
  }, [timelineDuration]);

  const tickStep = timelineDuration > 300 ? 60 : 30;
  const ticks = useMemo(() => {
    const list: number[] = [];
    for (let time = 0; time <= timelineDuration; time += tickStep) list.push(time);
    return list;
  }, [timelineDuration, tickStep]);

  const selectedLane = lanes.find((lane) => lane.id === selected) ?? null;
  const canSplit = Boolean(
    selectedLane &&
      playhead > selectedLane.start + MIN_CLIP &&
      playhead < selectedLane.start + selectedLane.duration - MIN_CLIP
  );

  const commitLanes = useCallback(
    (next: Clip[]) => {
      setHistory((current) => [...current.slice(-40), lanes]);
      setFuture([]);
      setLanes(next);
      setSelected((current) =>
        current && next.some((lane) => lane.id === current) ? current : next[0]?.id ?? null
      );
    },
    [lanes]
  );

  const updateLane = useCallback(
    (id: string, patch: Partial<Clip>) => {
      commitLanes(lanes.map((lane) => (lane.id === id ? { ...lane, ...patch } : lane)));
    },
    [commitLanes, lanes]
  );

  const undo = useCallback(() => {
    setHistory((current) => {
      const previous = current[current.length - 1];
      if (!previous) return current;
      setFuture((futureCurrent) => [lanes, ...futureCurrent.slice(0, 39)]);
      setLanes(previous);
      setSelected((selectedCurrent) =>
        selectedCurrent && previous.some((lane) => lane.id === selectedCurrent)
          ? selectedCurrent
          : previous[0]?.id ?? null
      );
      return current.slice(0, -1);
    });
  }, [lanes]);

  const redo = useCallback(() => {
    setFuture((current) => {
      const next = current[0];
      if (!next) return current;
      setHistory((historyCurrent) => [...historyCurrent.slice(-40), lanes]);
      setLanes(next);
      setSelected((selectedCurrent) =>
        selectedCurrent && next.some((lane) => lane.id === selectedCurrent)
          ? selectedCurrent
          : next[0]?.id ?? null
      );
      return current.slice(1);
    });
  }, [lanes]);

  const stopSources = useCallback(() => {
    for (const source of sourcesRef.current) {
      try {
        source.stop();
      } catch {
        /* already stopped */
      }
    }
    sourcesRef.current = [];
    nodesRef.current.clear();
    if (rafRef.current !== null) {
      cancelAnimationFrame(rafRef.current);
      rafRef.current = null;
    }
  }, []);

  useEffect(() => {
    return () => {
      stopSources();
      if (audioCtxRef.current) void audioCtxRef.current.close();
      audioCtxRef.current = null;
    };
  }, [stopSources]);

  useEffect(() => {
    if (masterGainRef.current) masterGainRef.current.gain.value = master / 100;
    const anySolo = lanes.some((lane) => lane.solo);
    for (const [id, node] of nodesRef.current.entries()) {
      const lane = lanes.find((item) => item.id === id);
      if (!lane) continue;
      const silent = lane.muted || (anySolo && !lane.solo);
      node.gain.gain.value = silent ? 0 : lane.volume / 100;
      node.panner.pan.value = clamp(lane.pan / 50, -1, 1);
    }
  }, [lanes, master]);

  const ensureAudioContext = useCallback((): AudioContext => {
    if (audioCtxRef.current) return audioCtxRef.current;
    const context = new AudioContext();
    const gain = context.createGain();
    gain.gain.value = master / 100;
    gain.connect(context.destination);
    audioCtxRef.current = context;
    masterGainRef.current = gain;
    return context;
  }, [master]);

  const loadBuffer = useCallback(
    async (lane: Clip): Promise<AudioBuffer> => {
      const key = `${lane.generationId}:${lane.variant}`;
      const cached = buffersRef.current.get(key);
      if (cached) return cached;
      const context = ensureAudioContext();
      const blob = await fetchWebMusicClipBlob(lane.generationId, lane.variant);
      const buffer = await context.decodeAudioData(await blob.arrayBuffer());
      buffersRef.current.set(key, buffer);
      return buffer;
    },
    [ensureAudioContext]
  );

  const startPlayback = useCallback(
    async (from: number) => {
      const context = ensureAudioContext();
      await context.resume();
      stopSources();
      setAudioError("");
      setAudioLoading(true);
      const anySolo = lanes.some((lane) => lane.solo);
      const audible = lanes.filter((lane) => !lane.muted && (!anySolo || lane.solo));
      if (!audible.length) {
        setAudioLoading(false);
        setPlaying(true);
        const startedAt = context.currentTime + 0.05;
        startedAtRef.current = startedAt;
        startPlayheadRef.current = from;
        const tick = () => {
          const next = from + Math.max(0, context.currentTime - startedAt);
          setPlayhead(Math.min(timelineDurationRef.current, next));
          if (next >= timelineDurationRef.current) {
            stopSources();
            setPlaying(false);
            return;
          }
          rafRef.current = requestAnimationFrame(tick);
        };
        rafRef.current = requestAnimationFrame(tick);
        return;
      }

      try {
        const loaded = await Promise.all(
          audible.map(async (lane) => ({ lane, buffer: await loadBuffer(lane) }))
        );
        const startAt = context.currentTime + 0.06;
        const masterGain = masterGainRef.current;
        if (!masterGain) return;
        for (const { lane, buffer } of loaded) {
          if (from >= lane.start + lane.duration) continue;
          const elapsedInClip = from > lane.start ? from - lane.start : 0;
          const offset = lane.offset + elapsedInClip;
          const remaining = Math.min(lane.duration - elapsedInClip, buffer.duration - offset);
          if (remaining <= 0 || offset >= buffer.duration) continue;
          const source = context.createBufferSource();
          source.buffer = buffer;
          const gain = context.createGain();
          const panner = context.createStereoPanner();
          gain.gain.value = lane.volume / 100;
          panner.pan.value = clamp(lane.pan / 50, -1, 1);
          source.connect(gain);
          gain.connect(panner);
          panner.connect(masterGain);
          source.start(startAt + Math.max(0, lane.start - from), offset, remaining);
          sourcesRef.current.push(source);
          nodesRef.current.set(lane.id, { gain, panner });
        }
        startedAtRef.current = startAt;
        startPlayheadRef.current = from;
        setPlaying(true);
        const tick = () => {
          const next = from + Math.max(0, context.currentTime - startAt);
          setPlayhead(Math.min(timelineDurationRef.current, next));
          if (next >= timelineDurationRef.current) {
            stopSources();
            setPlaying(false);
            return;
          }
          rafRef.current = requestAnimationFrame(tick);
        };
        rafRef.current = requestAnimationFrame(tick);
      } catch (cause) {
        stopSources();
        setPlaying(false);
        setAudioError(cause instanceof Error ? cause.message : "Could not load studio audio");
      } finally {
        setAudioLoading(false);
      }
    },
    [ensureAudioContext, lanes, loadBuffer, stopSources]
  );

  const seekTo = useCallback(
    (seconds: number) => {
      const next = clamp(seconds, 0, timelineDurationRef.current);
      setPlayhead(next);
      if (playing) {
        stopSources();
        void startPlayback(next);
      }
    },
    [playing, startPlayback, stopSources]
  );

  const togglePlay = useCallback(() => {
    if (!lanes.length) return;
    if (playing) {
      stopSources();
      setPlaying(false);
      return;
    }
    if (mainPlaying) toggleMainPlayer();
    void startPlayback(playheadRef.current >= timelineDurationRef.current ? 0 : playheadRef.current);
  }, [lanes.length, mainPlaying, playing, startPlayback, stopSources, toggleMainPlayer]);

  useEffect(() => {
    const handleKey = (event: KeyboardEvent) => {
      const target = event.target as HTMLElement | null;
      if (target?.closest("input, textarea, select, button, a, [contenteditable='true']")) return;
      if (event.code === "Space") {
        event.preventDefault();
        togglePlay();
      }
      if (event.key === "Delete" || event.key === "Backspace") {
        if (!selected) return;
        event.preventDefault();
        commitLanes(lanes.filter((lane) => lane.id !== selected));
      }
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "z") {
        event.preventDefault();
        if (event.shiftKey) redo();
        else undo();
      }
    };
    window.addEventListener("keydown", handleKey);
    return () => window.removeEventListener("keydown", handleKey);
  }, [commitLanes, lanes, redo, selected, togglePlay, undo]);

  useEffect(() => {
    const handleMove = (event: PointerEvent) => {
      const drag = dragRef.current;
      if (!drag || !drag.trackWidth) return;
      const deltaSeconds = ((event.clientX - drag.startX) / drag.trackWidth) * timelineDurationRef.current;
      if (drag.mode === "move") {
        const nextStart = clamp(snap(drag.start + deltaSeconds), 0, timelineDurationRef.current - drag.duration);
        setLanes((current) =>
          current.map((lane) => (lane.id === drag.id ? { ...lane, start: nextStart } : lane))
        );
        return;
      }
      if (drag.mode === "left") {
        const minStart = Math.max(0, drag.start - drag.offset);
        const nextStart = clamp(
          snap(drag.start + deltaSeconds),
          minStart,
          drag.start + drag.duration - MIN_CLIP
        );
        const nextDuration = drag.duration - (nextStart - drag.start);
        setLanes((current) =>
          current.map((lane) =>
            lane.id === drag.id
              ? {
                  ...lane,
                  start: nextStart,
                  duration: nextDuration,
                  offset: drag.offset + (nextStart - drag.start),
                }
              : lane
          )
        );
        return;
      }
      const nextDuration = clamp(
        snap(drag.duration + deltaSeconds),
        MIN_CLIP,
        timelineDurationRef.current - drag.start
      );
      setLanes((current) =>
        current.map((lane) => (lane.id === drag.id ? { ...lane, duration: nextDuration } : lane))
      );
    };
    const handleUp = () => {
      dragRef.current = null;
    };
    window.addEventListener("pointermove", handleMove);
    window.addEventListener("pointerup", handleUp);
    return () => {
      window.removeEventListener("pointermove", handleMove);
      window.removeEventListener("pointerup", handleUp);
    };
  }, []);

  function beginDrag(event: ReactPointerEvent, lane: Clip, mode: DragState["mode"]) {
    event.preventDefault();
    event.stopPropagation();
    setSelected(lane.id);
    setHistory((current) => [...current.slice(-40), lanes]);
    setFuture([]);
    const track = event.currentTarget.closest(".studio-lane-track") as HTMLElement | null;
    if (!track) return;
    dragRef.current = {
      id: lane.id,
      mode,
      startX: event.clientX,
      start: lane.start,
      duration: lane.duration,
      offset: lane.offset,
      trackWidth: track.getBoundingClientRect().width,
    };
  }

  function addGeneration(item: WebMusicGeneration) {
    const existing = lanes.find((lane) => lane.generationId === item.id);
    if (existing) {
      setSelected(existing.id);
      return;
    }
    const lane = clipFromGeneration(item, lanes.length, clamp(playhead, 0, timelineDuration - 20));
    if (!lane) return;
    commitLanes([...lanes, lane]);
    setSelected(lane.id);
  }

  function duplicateSelected() {
    if (!selectedLane) return;
    const copy: Clip = {
      ...selectedLane,
      id: makeId(),
      start: clamp(selectedLane.start + 2, 0, timelineDuration - selectedLane.duration),
      color: COLORS[lanes.length % COLORS.length],
    };
    commitLanes([...lanes, copy]);
    setSelected(copy.id);
  }

  function splitSelected() {
    if (!selectedLane) return;
    const local = playhead - selectedLane.start;
    if (local <= MIN_CLIP || local >= selectedLane.duration - MIN_CLIP) return;
    const left: Clip = { ...selectedLane, duration: local };
    const right: Clip = {
      ...selectedLane,
      id: makeId(),
      start: playhead,
      duration: selectedLane.duration - local,
      offset: selectedLane.offset + local,
    };
    commitLanes(lanes.flatMap((lane) => (lane.id === selectedLane.id ? [left, right] : [lane])));
    setSelected(right.id);
  }

  function deleteSelected() {
    if (!selectedLane) return;
    commitLanes(lanes.filter((lane) => lane.id !== selectedLane.id));
  }

  function seekFromEvent(event: ReactPointerEvent<HTMLElement>) {
    const rect = event.currentTarget.getBoundingClientRect();
    const ratio = clamp((event.clientX - rect.left) / rect.width, 0, 1);
    seekTo(ratio * timelineDuration);
  }

  const totalMinutes = Math.floor(
    lanes.reduce((max, lane) => Math.max(max, lane.start + lane.duration), 0) / 60
  );

  if (authLoading) {
    return <p className="fine" style={{ textAlign: "left" }}>Loading studio…</p>;
  }

  if (!user) {
    return (
      <div className="page">
        <div className="invite-signin panel">
          <span className="invite-hero-icon"><Icon name="fa-table-columns" /></span>
          <h1>Studio</h1>
          <p>Sign in to open your tracks in the Camxora Studio editor.</p>
          <Link className="btn btn-primary" href="/login?next=/studio/editor">Sign in</Link>
        </div>
      </div>
    );
  }

  return (
    <div className="page studio-editor-page">
      <div className="studio-editor-head">
        <div className="studio-session-title">
          <div className="eyebrow">Studio</div>
          <input
            value={sessionName}
            onChange={(event) => setSessionName(event.target.value)}
            aria-label="Session name"
            maxLength={80}
          />
          <span>
            {savedAt ? "Saved locally" : "Local session"} · {lanes.length}{" "}
            {lanes.length === 1 ? "track" : "tracks"}
            {totalMinutes > 0 ? ` · ${totalMinutes}m arrangement` : ""}
          </span>
        </div>
        <div className="page-actions">
          <button
            className="btn btn-ghost"
            type="button"
            onClick={() => {
              if (!window.confirm("Clear this session? This does not delete your songs.")) return;
              commitLanes([]);
              setSelected(null);
              setPlayhead(0);
            }}
          >
            New session
          </button>
          <Link className="btn btn-ghost" href="/create">Create a track</Link>
          <button className="btn btn-primary" type="button" disabled title="Render engine not connected yet">
            <Icon name="fa-download" /> Export
          </button>
        </div>
      </div>

      <div className="studio-toolbar">
        <button className="studio-icon-btn" type="button" aria-label="Undo" onClick={undo} disabled={!history.length} title="Undo (Ctrl+Z)">
          <Icon name="fa-rotate-left" />
        </button>
        <button className="studio-icon-btn" type="button" aria-label="Redo" onClick={redo} disabled={!future.length} title="Redo (Ctrl+Shift+Z)">
          <Icon name="fa-rotate-right" />
        </button>
        <span className="studio-toolbar-divider" />
        <button className="studio-icon-btn" type="button" aria-label="Split at playhead" onClick={splitSelected} disabled={!canSplit} title="Split at playhead">
          <Icon name="fa-scissors" />
        </button>
        <button className="studio-icon-btn" type="button" aria-label="Duplicate clip" onClick={duplicateSelected} disabled={!selectedLane} title="Duplicate clip">
          <Icon name="fa-copy" />
        </button>
        <span className="studio-toolbar-divider" />
        <label className="studio-bpm">BPM <input type="number" min={40} max={220} value={bpm} onChange={(event) => setBpm(clamp(Number(event.target.value), 40, 220))} /></label>
        <label className="studio-zoom">Zoom <input type="range" min="0.7" max="2" step="0.1" value={zoom} onChange={(event) => setZoom(Number(event.target.value))} /></label>
        <span className="studio-toolbar-spacer" />
        <span className="studio-time">{formatTime(playhead)} / {formatTime(timelineDuration)}</span>
      </div>

      <div className="studio-work">
        <aside className="studio-library">
          <div className="sec-head"><h2>Library</h2><Link href="/library">All</Link></div>
          {!items.length ? (
            <div className="studio-library-empty">
              <Icon name="fa-music" />
              <p>No generated tracks yet.</p>
              <Link className="btn btn-ghost" href="/create">Create one</Link>
            </div>
          ) : (
            <div className="studio-library-list">
              {items.map((item) => {
                const clip = item.clips?.find((entry) => entry.ready) ?? item.clips?.[0];
                const added = lanes.some((lane) => lane.generationId === item.id);
                return (
                  <button
                    key={item.id}
                    type="button"
                    className={`studio-lib-item${added ? " added" : ""}`}
                    onClick={() => addGeneration(item)}
                    title={added ? "Already in session — click to select" : "Add to session"}
                  >
                    <span className="studio-lib-cover">
                      {clip?.image_url ? <img src={clip.image_url} alt="" loading="lazy" /> : <Icon name="fa-music" />}
                    </span>
                    <span>
                      <b>{item.title || "Untitled"}</b>
                      <small>{item.style || "Camxora"}</small>
                    </span>
                    <Icon name={added ? "fa-check" : "fa-plus"} />
                  </button>
                );
              })}
            </div>
          )}
        </aside>

        <section className="studio-timeline">
          <div className="studio-ruler">
            <span className="studio-ruler-gutter" />
            <div className="studio-ruler-track" style={{ zoom } as CSSProperties} onPointerDown={seekFromEvent}>
              {ticks.map((tick) => (
                <span key={tick} style={{ left: `${(tick / timelineDuration) * 100}%` }}>
                  {formatTime(tick)}
                </span>
              ))}
            </div>
            <span />
          </div>
          <div className="studio-lanes" style={{ zoom } as CSSProperties}>
            {lanes.map((lane, index) => (
              <div className={`studio-lane${selected === lane.id ? " selected" : ""}`} key={lane.id}>
                <button className="studio-lane-head" type="button" onClick={() => setSelected(lane.id)}>
                  <span className="studio-lane-dot" style={{ background: lane.color }} />
                  <span className="studio-lane-copy">
                    <b>{lane.title}</b>
                    <small>Track {index + 1} · {formatTime(lane.start)}</small>
                  </span>
                </button>
                <div
                  className="studio-lane-track"
                  style={{
                    backgroundSize: `${(tickStep / timelineDuration) * 100}% 100%`,
                  }}
                  onPointerDown={seekFromEvent}
                >
                  <button
                    className={`studio-clip${selected === lane.id ? " selected" : ""}`}
                    type="button"
                    style={{
                      left: `${(lane.start / timelineDuration) * 100}%`,
                      width: `${(lane.duration / timelineDuration) * 100}%`,
                      borderColor: lane.color,
                      background: `linear-gradient(180deg, ${lane.color}44, ${lane.color}22)`,
                    }}
                    onPointerDown={(event) => beginDrag(event, lane, "move")}
                    onClick={() => setSelected(lane.id)}
                  >
                    <span className="studio-clip-color" style={{ background: lane.color }} />
                    <span className="studio-clip-copy">
                      <b>{lane.title}</b>
                      <small>{formatTime(lane.duration)}</small>
                    </span>
                    <span className="studio-waveform" aria-hidden="true">
                      {Array.from({ length: 32 }).map((_, bar) => (
                        <i
                          key={bar}
                          style={{
                            height: `${18 + ((bar * 17 + lane.title.length * 11 + index * 7) % 72)}%`,
                          }}
                        />
                      ))}
                    </span>
                    <span
                      className="studio-clip-handle left"
                      onPointerDown={(event) => beginDrag(event, lane, "left")}
                    />
                    <span
                      className="studio-clip-handle right"
                      onPointerDown={(event) => beginDrag(event, lane, "right")}
                    />
                  </button>
                </div>
                <div className="studio-lane-controls">
                  <button type="button" className={lane.muted ? "on" : ""} onClick={() => updateLane(lane.id, { muted: !lane.muted })}>M</button>
                  <button type="button" className={lane.solo ? "on" : ""} onClick={() => updateLane(lane.id, { solo: !lane.solo })}>S</button>
                  <button type="button" aria-label={`Remove ${lane.title}`} onClick={() => commitLanes(lanes.filter((item) => item.id !== lane.id))}><Icon name="fa-xmark" /></button>
                </div>
              </div>
            ))}
            {!lanes.length ? (
              <div className="studio-timeline-empty">
                <Icon name="fa-table-columns" />
                <h3>Your session is empty</h3>
                <p>Add a generated track from the library to start arranging.</p>
              </div>
            ) : null}
            <div className="studio-playhead-layer" aria-hidden="true">
              <span />
              <div className="studio-playhead-track">
                <i style={{ left: `${(playhead / timelineDuration) * 100}%` }} />
              </div>
              <span />
            </div>
          </div>
        </section>

        <aside className="studio-inspector">
          <div className="sec-head"><h2>Inspector</h2></div>
          {!selectedLane ? (
            <div className="studio-inspector-empty">
              <Icon name="fa-hand-pointer" />
              <p>Select a clip to edit its timing and mix.</p>
            </div>
          ) : (
            <>
              <div className="studio-inspector-title">
                <span style={{ background: selectedLane.color }} />
                <div><b>{selectedLane.title}</b><small>{selectedLane.style}</small></div>
              </div>
              <div className="studio-inspector-grid">
                <label>Start
                  <input type="number" min={0} step={0.5} value={Number(selectedLane.start.toFixed(1))} onChange={(event) => updateLane(selectedLane.id, { start: clamp(Number(event.target.value), 0, timelineDuration - selectedLane.duration) })} />
                </label>
                <label>Length
                  <input type="number" min={MIN_CLIP} step={0.5} value={Number(selectedLane.duration.toFixed(1))} onChange={(event) => updateLane(selectedLane.id, { duration: clamp(Number(event.target.value), MIN_CLIP, timelineDuration - selectedLane.start) })} />
                </label>
              </div>
              <label className="studio-slider">Volume <b>{selectedLane.volume}%</b>
                <input type="range" min="0" max="100" value={selectedLane.volume} onChange={(event) => updateLane(selectedLane.id, { volume: Number(event.target.value) })} />
              </label>
              <label className="studio-slider">Pan <b>{selectedLane.pan === 0 ? "C" : selectedLane.pan > 0 ? `R${selectedLane.pan}` : `L${Math.abs(selectedLane.pan)}`}</b>
                <input type="range" min="-50" max="50" value={selectedLane.pan} onChange={(event) => updateLane(selectedLane.id, { pan: Number(event.target.value) })} />
              </label>
              <div className="studio-inspector-actions">
                <button className={selectedLane.muted ? "on" : ""} type="button" onClick={() => updateLane(selectedLane.id, { muted: !selectedLane.muted })}>Mute</button>
                <button className={selectedLane.solo ? "on" : ""} type="button" onClick={() => updateLane(selectedLane.id, { solo: !selectedLane.solo })}>Solo</button>
              </div>
              <div className="studio-inspector-actions">
                <button type="button" onClick={splitSelected} disabled={!canSplit}>Split</button>
                <button type="button" onClick={duplicateSelected}>Duplicate</button>
              </div>
              <button className="studio-inspector-delete" type="button" onClick={deleteSelected}>
                <Icon name="fa-trash" /> Remove from session
              </button>
              <div className="studio-inspector-note">
                <Icon name="fa-circle-info" /> Preview mix only. Export needs the render engine.
              </div>
            </>
          )}
        </aside>
      </div>

      <div className="studio-transport">
        <span className="studio-transport-left"><Icon name="fa-wave-square" /> {bpm} BPM · 4/4</span>
        <div className="studio-transport-center">
          <button type="button" aria-label="Go to start" onClick={() => seekTo(0)}><Icon name="fa-backward-step" /></button>
          <button className="play" type="button" aria-label={playing ? "Pause" : "Play"} onClick={togglePlay} disabled={audioLoading || !lanes.length}>
            <Icon name={audioLoading ? "fa-spinner" : playing ? "fa-pause" : "fa-play"} />
          </button>
          <button type="button" aria-label="Go to end" onClick={() => seekTo(timelineDuration)}><Icon name="fa-forward-step" /></button>
        </div>
        <div className="studio-transport-right">
          <span className="studio-transport-time">{formatTime(playhead)}</span>
          <span className="studio-master">
            <Icon name="fa-volume-high" />
            <input type="range" min="0" max="100" value={master} onChange={(event) => setMaster(Number(event.target.value))} aria-label="Master volume" />
            <b>{master}%</b>
          </span>
        </div>
      </div>
      {audioError ? <p className="studio-audio-error" role="alert">{audioError}</p> : null}
      {audioLoading ? <p className="studio-audio-status" role="status">Loading studio audio…</p> : null}
    </div>
  );
}
