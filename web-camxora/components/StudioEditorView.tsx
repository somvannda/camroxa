"use client";

import Link from "next/link";
import { Mp3Encoder } from "@breezystack/lamejs";
import JSZip from "jszip";
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
import { fetchWebMusicClipBlob, saveBlob } from "@/lib/web-music-api";
import {
  createStudioProject,
  getStudioProject,
  listStudioProjects,
  updateStudioProject,
  type StudioProjectData,
  type StudioOperation,
  requestStudioStems,
  requestStudioExtend,
  requestStudioCover,
  requestStudioAddVocals,
  requestStudioAddInstrumental,
  requestStudioReplaceSection,
  getStudioOperation,
  getStudioPricing,
  type StudioPricing,
} from "@/lib/studio-api";

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
  fadeIn: number;
  fadeOut: number;
  audioUrl?: string | null;
  low: number;
  mid: number;
  high: number;
  delay: number;
  reverb: number;
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
  loopStart?: number;
  loopEnd?: number;
  lanes?: Clip[];
};

type AudioMeta = {
  peaks: number[];
  duration: number;
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

function computePeaks(buffer: AudioBuffer, bins = 56): number[] {
  const channel = buffer.getChannelData(0);
  const chunk = Math.max(1, Math.floor(channel.length / bins));
  const peaks: number[] = [];
  for (let bin = 0; bin < bins; bin += 1) {
    const start = bin * chunk;
    const end = Math.min(channel.length, start + chunk);
    let peak = 0;
    for (let index = start; index < end; index += 1) {
      peak = Math.max(peak, Math.abs(channel[index]));
    }
    peaks.push(peak);
  }
  const maximum = Math.max(0.0001, ...peaks);
  return peaks.map((value) => Math.max(0.03, Math.pow(value / maximum, 1.6)));
}

function syntheticPeaks(lane: Clip, index: number, bins = 32): number[] {
  return Array.from({ length: bins }, (_, bar) => {
    const value = 18 + ((bar * 17 + lane.title.length * 11 + index * 7) % 72);
    return value / 100;
  });
}

function waveformPeaks(lane: Clip, meta: AudioMeta | undefined, index: number): number[] {
  if (!meta || !meta.duration) return syntheticPeaks(lane, index);
  const start = Math.floor((lane.offset / meta.duration) * meta.peaks.length);
  const end = Math.ceil(((lane.offset + lane.duration) / meta.duration) * meta.peaks.length);
  const sliced = meta.peaks.slice(Math.max(0, start), Math.max(start + 1, end));
  return sliced.length ? sliced : syntheticPeaks(lane, index);
}

function encodeWav(buffer: AudioBuffer): Blob {
  const channels = buffer.numberOfChannels;
  const sampleRate = buffer.sampleRate;
  const frames = buffer.length;
  const bytesPerSample = 2;
  const dataSize = frames * channels * bytesPerSample;
  const output = new ArrayBuffer(44 + dataSize);
  const view = new DataView(output);
  const writeString = (offset: number, value: string) => {
    for (let index = 0; index < value.length; index += 1) {
      view.setUint8(offset + index, value.charCodeAt(index));
    }
  };
  writeString(0, "RIFF");
  view.setUint32(4, 36 + dataSize, true);
  writeString(8, "WAVE");
  writeString(12, "fmt ");
  view.setUint32(16, 16, true);
  view.setUint16(20, 1, true);
  view.setUint16(22, channels, true);
  view.setUint32(24, sampleRate, true);
  view.setUint32(28, sampleRate * channels * bytesPerSample, true);
  view.setUint16(32, channels * bytesPerSample, true);
  view.setUint16(34, 16, true);
  writeString(36, "data");
  view.setUint32(40, dataSize, true);
  const channelData = Array.from({ length: channels }, (_, channel) => buffer.getChannelData(channel));
  let offset = 44;
  for (let frame = 0; frame < frames; frame += 1) {
    for (let channel = 0; channel < channels; channel += 1) {
      const sample = clamp(channelData[channel][frame], -1, 1);
      view.setInt16(offset, sample < 0 ? sample * 0x8000 : sample * 0x7fff, true);
      offset += bytesPerSample;
    }
  }
  return new Blob([output], { type: "audio/wav" });
}

async function encodeMp3(buffer: AudioBuffer, kbps = 192): Promise<Blob> {
  const channels = Math.min(2, buffer.numberOfChannels);
  const encoder = new Mp3Encoder(channels, buffer.sampleRate, kbps);
  const left = buffer.getChannelData(0);
  const right = channels > 1 ? buffer.getChannelData(1) : left;
  const blockSize = 1152;
  const leftPcm = new Int16Array(blockSize);
  const rightPcm = new Int16Array(blockSize);
  const chunks: BlobPart[] = [];
  let blockIndex = 0;
  for (let offset = 0; offset < buffer.length; offset += blockSize) {
    const length = Math.min(blockSize, buffer.length - offset);
    for (let index = 0; index < length; index += 1) {
      leftPcm[index] = clamp(left[offset + index], -1, 1) * 0x7fff;
      if (channels > 1) rightPcm[index] = clamp(right[offset + index], -1, 1) * 0x7fff;
    }
    const encoded = channels > 1
      ? encoder.encodeBuffer(leftPcm, rightPcm)
      : encoder.encodeBuffer(leftPcm);
    if (encoded.length) chunks.push(new Uint8Array(encoded));
    blockIndex += 1;
    if (blockIndex % 120 === 0) {
      await new Promise((resolve) => window.setTimeout(resolve, 0));
    }
  }
  const tail = encoder.flush();
  if (tail.length) chunks.push(new Uint8Array(tail));
  return new Blob(chunks, { type: "audio/mpeg" });
}

function scheduleClipGain(
  gain: GainNode,
  base: number,
  lane: Clip,
  from: number,
  when: number,
  length: number
) {
  const elapsed = Math.max(0, from - lane.start);
  const fadeIn = Math.min(lane.fadeIn, length / 2);
  const fadeOut = Math.min(lane.fadeOut, length / 2);
  if (fadeIn > 0 && elapsed < fadeIn) {
    const startLevel = base * (elapsed / fadeIn);
    gain.gain.setValueAtTime(startLevel, when);
    gain.gain.linearRampToValueAtTime(base, when + (fadeIn - elapsed));
  } else {
    gain.gain.setValueAtTime(base, when);
  }
  if (fadeOut > 0) {
    gain.gain.setValueAtTime(base, when + Math.max(0, length - fadeOut));
    gain.gain.linearRampToValueAtTime(0, when + length);
  }
}

function makeReverbImpulse(context: BaseAudioContext): AudioBuffer {
  const seconds = 1.8;
  const length = Math.max(1, Math.floor(context.sampleRate * seconds));
  const impulse = context.createBuffer(2, length, context.sampleRate);
  for (let channel = 0; channel < 2; channel += 1) {
    const data = impulse.getChannelData(channel);
    for (let index = 0; index < length; index += 1) {
      data[index] = (Math.random() * 2 - 1) * Math.pow(1 - index / length, 2.4);
    }
  }
  return impulse;
}

function connectTrackFx(
  context: BaseAudioContext,
  input: AudioNode,
  master: AudioNode,
  lane: Clip
): { delayWet: GainNode; reverbWet: GainNode } {
  const dry = context.createGain();
  dry.gain.value = 1;
  input.connect(dry);
  dry.connect(master);

  const delay = context.createDelay(1);
  delay.delayTime.value = 0.28;
  const feedback = context.createGain();
  feedback.gain.value = 0.26;
  const delayWet = context.createGain();
  delayWet.gain.value = lane.delay / 100;
  input.connect(delay);
  delay.connect(feedback);
  feedback.connect(delay);
  delay.connect(delayWet);
  delayWet.connect(master);

  const convolver = context.createConvolver();
  convolver.buffer = makeReverbImpulse(context);
  const reverbWet = context.createGain();
  reverbWet.gain.value = lane.reverb / 100;
  input.connect(convolver);
  convolver.connect(reverbWet);
  reverbWet.connect(master);

  return { delayWet, reverbWet };
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
    fadeIn: 0,
    fadeOut: 0,
    audioUrl: null,
    low: 0,
    mid: 0,
    high: 0,
    delay: 0,
    reverb: 0,
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
  const [audioMeta, setAudioMeta] = useState<Record<string, AudioMeta>>({});
  const [search, setSearch] = useState("");
  const [selected, setSelected] = useState<string | null>(null);
  const [sessionName, setSessionName] = useState("Untitled session");
  const [bpm, setBpm] = useState(90);
  const [zoom, setZoom] = useState(1);
  const [master, setMaster] = useState(80);
  const [playhead, setPlayhead] = useState(0);
  const [playing, setPlaying] = useState(false);
  const [audioLoading, setAudioLoading] = useState(false);
  const [audioError, setAudioError] = useState("");
  const [exporting, setExporting] = useState(false);
  const [exportError, setExportError] = useState("");
  const [exportFormat, setExportFormat] = useState<"wav" | "mp3">("wav");
  const [exportRange, setExportRange] = useState<"full" | "loop">("full");
  const [loop, setLoop] = useState(false);
  const [loopStart, setLoopStart] = useState(0);
  const [loopEnd, setLoopEnd] = useState(60);
  const [loaded, setLoaded] = useState(false);
  const [savedAt, setSavedAt] = useState<Date | null>(null);
  const [projectId, setProjectId] = useState<string | null>(null);
  const [cloudState, setCloudState] = useState<"local" | "saving" | "saved" | "error">("local");
  const [cloudError, setCloudError] = useState("");
  const [stemsBusy, setStemsBusy] = useState(false);
  const [stemsStatus, setStemsStatus] = useState("");
  const [stemsError, setStemsError] = useState("");
  const [editBusy, setEditBusy] = useState(false);
  const [editStatus, setEditStatus] = useState("");
  const [editError, setEditError] = useState("");
  const [editPrompt, setEditPrompt] = useState("");
  const [replaceLyrics, setReplaceLyrics] = useState("");
  const [studioPricing, setStudioPricing] = useState<StudioPricing | null>(null);
  const [history, setHistory] = useState<Clip[][]>([]);
  const [future, setFuture] = useState<Clip[][]>([]);
  const dragRef = useRef<DragState | null>(null);
  const loopRef = useRef(false);
  const loopStartRef = useRef(0);
  const loopEndRef = useRef(60);
  const loopDragRef = useRef<{ which: "start" | "end"; startX: number; start: number; end: number; width: number } | null>(null);
  const startPlaybackRef = useRef<(from: number) => Promise<void>>(async () => {});
  const playheadRef = useRef(0);
  const timelineDurationRef = useRef(180);
  const audioCtxRef = useRef<AudioContext | null>(null);
  const masterGainRef = useRef<GainNode | null>(null);
  const buffersRef = useRef<Map<string, AudioBuffer>>(new Map());
  const sourcesRef = useRef<AudioBufferSourceNode[]>([]);
  const nodesRef = useRef<Map<string, { gain: GainNode; panner: StereoPannerNode; low: BiquadFilterNode; mid: BiquadFilterNode; high: BiquadFilterNode; delayWet: GainNode; reverbWet: GainNode }>>(new Map());
  const startedAtRef = useRef(0);
  const startPlayheadRef = useRef(0);
  const rafRef = useRef<number | null>(null);

  const storageKey = user ? `${STORAGE_PREFIX}:${user.id}` : "";
  const cloudSaveRef = useRef(false);

  useEffect(() => {
    playheadRef.current = playhead;
  }, [playhead]);

  useEffect(() => {
    loopRef.current = loop;
  }, [loop]);

  useEffect(() => {
    loopStartRef.current = loopStart;
    loopEndRef.current = loopEnd;
  }, [loopStart, loopEnd]);

  useEffect(() => {
    if (!user) return;
    let alive = true;
    void getStudioPricing()
      .then((pricing) => {
        if (alive) setStudioPricing(pricing);
      })
      .catch(() => {
        if (alive) setStudioPricing(null);
      });
    return () => {
      alive = false;
    };
  }, [user]);

  function normalizeLanes(input: unknown): Clip[] {
    if (!Array.isArray(input)) return [];
    return input
      .filter(
        (lane): lane is Clip =>
          Boolean(lane) &&
          typeof lane === "object" &&
          typeof (lane as Clip).id === "string" &&
          typeof (lane as Clip).generationId === "string" &&
          Number.isFinite((lane as Clip).start) &&
          Number.isFinite((lane as Clip).duration)
      )
      .map((lane) => ({
        ...lane,
        fadeIn: Number.isFinite(lane.fadeIn) ? Math.max(0, Number(lane.fadeIn)) : 0,
        fadeOut: Number.isFinite(lane.fadeOut) ? Math.max(0, Number(lane.fadeOut)) : 0,
        low: Number.isFinite(lane.low) ? clamp(Number(lane.low), -12, 12) : 0,
        mid: Number.isFinite(lane.mid) ? clamp(Number(lane.mid), -12, 12) : 0,
        high: Number.isFinite(lane.high) ? clamp(Number(lane.high), -12, 12) : 0,
        delay: Number.isFinite(lane.delay) ? clamp(Number(lane.delay), 0, 100) : 0,
        reverb: Number.isFinite(lane.reverb) ? clamp(Number(lane.reverb), 0, 100) : 0,
      }));
  }

  function applySession(saved: StoredSession, nextProjectId: string | null) {
    const savedLanes = normalizeLanes(saved.lanes);
    setLanes(savedLanes);
    setSelected(savedLanes[0]?.id ?? null);
    if (saved.name) setSessionName(saved.name);
    if (Number.isFinite(saved.bpm)) setBpm(clamp(Number(saved.bpm), 40, 220));
    if (Number.isFinite(saved.zoom)) setZoom(clamp(Number(saved.zoom), 0.7, 2));
    if (Number.isFinite(saved.master)) setMaster(clamp(Number(saved.master), 0, 100));
    if (Number.isFinite(saved.loopStart)) setLoopStart(Math.max(0, Number(saved.loopStart)));
    if (Number.isFinite(saved.loopEnd)) setLoopEnd(Math.max(1, Number(saved.loopEnd)));
    setProjectId(nextProjectId);
    setCloudState(nextProjectId ? "saved" : "local");
  }

  useEffect(() => {
    if (authLoading || !user) return;
    let active = true;
    setLoaded(false);
    fetchGenerations(100)
      .then(async (next) => {
        if (!active) return;
        setItems(next);
        try {
          const projects = await listStudioProjects(1, 0);
          const first = projects.items[0];
          if (first) {
            const project = await getStudioProject(first.id);
            if (!active) return;
            const data = (project.data || {}) as StudioProjectData;
            applySession(
              {
                name: project.title,
                bpm: project.bpm,
                zoom: Number.isFinite(data.zoom) ? Number(data.zoom) : 1,
                master: Number.isFinite(data.master) ? Number(data.master) : 80,
                loopStart: Number.isFinite(data.loopStart) ? Number(data.loopStart) : 0,
                loopEnd: Number.isFinite(data.loopEnd) ? Number(data.loopEnd) : 60,
                lanes: normalizeLanes(data.lanes),
              },
              project.id
            );
            return;
          }
        } catch {
          /* fall back to local */
        }
        if (!active) return;
        const raw = storageKey ? window.localStorage.getItem(storageKey) : null;
        if (raw) {
          try {
            applySession(JSON.parse(raw) as StoredSession, null);
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
      const payload: StoredSession = { name: sessionName, bpm, zoom, master, loopStart, loopEnd, lanes };
      window.localStorage.setItem(storageKey, JSON.stringify(payload));
      setSavedAt(new Date());
    }, 350);
    return () => window.clearTimeout(timer);
  }, [loaded, user, storageKey, sessionName, bpm, zoom, master, loopStart, loopEnd, lanes]);

  useEffect(() => {
    if (!loaded || !user || cloudSaveRef.current) return;
    if (!lanes.length && sessionName === "Untitled session") return;
    const timer = window.setTimeout(async () => {
      if (cloudSaveRef.current) return;
      cloudSaveRef.current = true;
      setCloudState("saving");
      setCloudError("");
      try {
        const data: StudioProjectData = { lanes, loopStart, loopEnd, zoom, master };
        if (projectId) {
          await updateStudioProject(projectId, {
            title: sessionName,
            bpm,
            time_signature: "4/4",
            data,
          });
        } else {
          const created = await createStudioProject({
            title: sessionName,
            major_version: 2,
            bpm,
            time_signature: "4/4",
            data,
          });
          setProjectId(created.id);
        }
        setCloudState("saved");
        setSavedAt(new Date());
      } catch (cause) {
        setCloudState("error");
        setCloudError(cause instanceof Error ? cause.message : "Cloud save failed");
      } finally {
        cloudSaveRef.current = false;
      }
    }, 650);
    return () => window.clearTimeout(timer);
  }, [loaded, user, projectId, sessionName, bpm, zoom, master, loopStart, loopEnd, lanes]);

  const timelineDuration = useMemo(() => {
    const end = lanes.reduce((max, lane) => Math.max(max, lane.start + lane.duration), 0);
    return Math.max(240, Math.ceil(Math.max(end, playhead + 10) / 30) * 30);
  }, [lanes, playhead]);

  useEffect(() => {
    timelineDurationRef.current = timelineDuration;
    setLoopEnd((current) => Math.min(current, timelineDuration));
    setLoopStart((current) => Math.min(current, Math.max(0, timelineDuration - 5)));
  }, [timelineDuration]);

  const tickStep = timelineDuration > 300 ? 60 : 30;
  const ticks = useMemo(() => {
    const list: number[] = [];
    for (let time = 0; time <= timelineDuration; time += tickStep) list.push(time);
    return list;
  }, [timelineDuration, tickStep]);

  const filteredItems = useMemo(() => {
    const query = search.trim().toLowerCase();
    if (!query) return items;
    return items.filter((item) =>
      `${item.title} ${item.style || ""}`.toLowerCase().includes(query)
    );
  }, [items, search]);

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
      node.low.gain.value = lane.low;
      node.mid.gain.value = lane.mid;
      node.high.gain.value = lane.high;
      node.delayWet.gain.value = lane.delay / 100;
      node.reverbWet.gain.value = lane.reverb / 100;
    }
  }, [lanes, master]);

  const ensureAudioContext = useCallback((): AudioContext => {
    if (audioCtxRef.current) return audioCtxRef.current;
    const context = new AudioContext();
    const gain = context.createGain();
    gain.gain.value = master / 100;
    const limiter = context.createDynamicsCompressor();
    limiter.threshold.value = -3;
    limiter.knee.value = 0;
    limiter.ratio.value = 20;
    limiter.attack.value = 0.003;
    limiter.release.value = 0.1;
    gain.connect(limiter);
    limiter.connect(context.destination);
    audioCtxRef.current = context;
    masterGainRef.current = gain;
    return context;
  }, [master]);

  const loadBuffer = useCallback(
    async (lane: Clip): Promise<AudioBuffer> => {
      const key = lane.audioUrl ? `url:${lane.audioUrl}` : `${lane.generationId}:${lane.variant}`;
      const cached = buffersRef.current.get(key);
      if (cached) return cached;
      const context = ensureAudioContext();
      let bytes: ArrayBuffer;
      if (lane.audioUrl) {
        const response = await fetch(lane.audioUrl, { credentials: "include" });
        if (!response.ok) throw new Error(`Could not load stem audio (${response.status}).`);
        bytes = await response.arrayBuffer();
      } else {
        const blob = await fetchWebMusicClipBlob(lane.generationId, lane.variant);
        bytes = await blob.arrayBuffer();
      }
      const buffer = await context.decodeAudioData(bytes);
      buffersRef.current.set(key, buffer);
      setAudioMeta((current) =>
        current[key]
          ? current
          : {
              ...current,
              [key]: { peaks: computePeaks(buffer), duration: buffer.duration },
            }
      );
      return buffer;
    },
    [ensureAudioContext]
  );

  const startPlayback = useCallback(
    async (from: number) => {
      if (loopRef.current && (from >= loopEndRef.current || from < loopStartRef.current)) {
        from = loopStartRef.current;
        setPlayhead(from);
      }
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
          if (next >= (loopRef.current ? loopEndRef.current : timelineDurationRef.current)) {
            stopSources();
            if (loopRef.current) {
              window.setTimeout(() => void startPlaybackRef.current(loopStartRef.current), 0);
            } else {
              setPlaying(false);
            }
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
          const low = context.createBiquadFilter();
          const mid = context.createBiquadFilter();
          const high = context.createBiquadFilter();
          low.type = "lowshelf";
          low.frequency.value = 250;
          low.gain.value = lane.low;
          mid.type = "peaking";
          mid.frequency.value = 1000;
          mid.Q.value = 1;
          mid.gain.value = lane.mid;
          high.type = "highshelf";
          high.frequency.value = 4000;
          high.gain.value = lane.high;
          panner.pan.value = clamp(lane.pan / 50, -1, 1);
          source.connect(low);
          low.connect(mid);
          mid.connect(high);
          high.connect(gain);
          gain.connect(panner);
          const fx = connectTrackFx(context, panner, masterGain, lane);
          const startWhen = startAt + Math.max(0, lane.start - from);
          scheduleClipGain(gain, lane.volume / 100, lane, from, startWhen, remaining);
          source.start(startWhen, offset, remaining);
          sourcesRef.current.push(source);
          nodesRef.current.set(lane.id, { gain, panner, low, mid, high, ...fx });
        }
        startedAtRef.current = startAt;
        startPlayheadRef.current = from;
        setPlaying(true);
        const tick = () => {
          const next = from + Math.max(0, context.currentTime - startAt);
          setPlayhead(Math.min(timelineDurationRef.current, next));
          if (next >= (loopRef.current ? loopEndRef.current : timelineDurationRef.current)) {
            stopSources();
            if (loopRef.current) {
              window.setTimeout(() => void startPlaybackRef.current(loopStartRef.current), 0);
            } else {
              setPlaying(false);
            }
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

  useEffect(() => {
    startPlaybackRef.current = startPlayback;
  }, [startPlayback]);

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
    const handleLoopMove = (event: PointerEvent) => {
      const drag = loopDragRef.current;
      if (!drag || !drag.width) return;
      const delta = ((event.clientX - drag.startX) / drag.width) * timelineDurationRef.current;
      if (drag.which === "start") {
        setLoopStart(clamp(snap(drag.start + delta), 0, drag.end - 5));
      } else {
        setLoopEnd(clamp(snap(drag.end + delta), drag.start + 5, timelineDurationRef.current));
      }
    };
    const handleLoopUp = () => {
      loopDragRef.current = null;
    };
    window.addEventListener("pointermove", handleLoopMove);
    window.addEventListener("pointerup", handleLoopUp);
    return () => {
      window.removeEventListener("pointermove", handleLoopMove);
      window.removeEventListener("pointerup", handleLoopUp);
    };
  }, []);

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

  function beginLoopDrag(event: ReactPointerEvent, which: "start" | "end") {
    event.preventDefault();
    event.stopPropagation();
    const track = event.currentTarget.closest(".studio-ruler-track") as HTMLElement | null;
    if (!track) return;
    loopDragRef.current = {
      which,
      startX: event.clientX,
      start: loopStart,
      end: loopEnd,
      width: track.getBoundingClientRect().width,
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
    const left: Clip = { ...selectedLane, duration: local, fadeOut: 0 };
    const right: Clip = {
      ...selectedLane,
      id: makeId(),
      start: playhead,
      duration: selectedLane.duration - local,
      offset: selectedLane.offset + local,
      fadeIn: 0,
    };
    commitLanes(lanes.flatMap((lane) => (lane.id === selectedLane.id ? [left, right] : [lane])));
    setSelected(right.id);
  }

  async function renderMix(options: {
    start: number;
    end: number;
    laneIds?: Set<string>;
  }): Promise<AudioBuffer> {
    const { start, end, laneIds } = options;
    const duration = Math.max(0, end - start);
    if (duration <= 0) throw new Error("Choose a valid export range.");
    const sampleRate = 44100;
    const offline = new OfflineAudioContext(2, Math.ceil(duration * sampleRate), sampleRate);
    const masterGain = offline.createGain();
    masterGain.gain.value = master / 100;
    const limiter = offline.createDynamicsCompressor();
    limiter.threshold.value = -3;
    limiter.knee.value = 0;
    limiter.ratio.value = 20;
    limiter.attack.value = 0.003;
    limiter.release.value = 0.1;
    masterGain.connect(limiter);
    limiter.connect(offline.destination);
    const anySolo = laneIds ? false : lanes.some((lane) => lane.solo);
    const audible = lanes.filter(
      (lane) =>
        (!laneIds || laneIds.has(lane.id)) &&
        !lane.muted &&
        (!anySolo || lane.solo || Boolean(laneIds?.has(lane.id)))
    );
    if (!audible.length) throw new Error("Every track is muted.");
    const loaded = await Promise.all(
      audible.map(async (lane) => ({ lane, buffer: await loadBuffer(lane) }))
    );
    for (const { lane, buffer } of loaded) {
      const clipStart = Math.max(lane.start, start);
      const clipEnd = Math.min(lane.start + lane.duration, end);
      if (clipEnd <= clipStart) continue;
      const offset = Math.max(0, Math.min(lane.offset + (clipStart - lane.start), buffer.duration));
      const available = Math.max(0, buffer.duration - offset);
      const length = Math.min(clipEnd - clipStart, available);
      if (length <= 0 || offset >= buffer.duration) continue;
      const source = offline.createBufferSource();
      source.buffer = buffer;
      const gain = offline.createGain();
      const panner = offline.createStereoPanner();
      const low = offline.createBiquadFilter();
      const mid = offline.createBiquadFilter();
      const high = offline.createBiquadFilter();
      low.type = "lowshelf";
      low.frequency.value = 250;
      low.gain.value = lane.low;
      mid.type = "peaking";
      mid.frequency.value = 1000;
      mid.Q.value = 1;
      mid.gain.value = lane.mid;
      high.type = "highshelf";
      high.frequency.value = 4000;
      high.gain.value = lane.high;
      panner.pan.value = clamp(lane.pan / 50, -1, 1);
      source.connect(low);
      low.connect(mid);
      mid.connect(high);
      high.connect(gain);
      gain.connect(panner);
      connectTrackFx(offline, panner, masterGain, lane);
      scheduleClipGain(
        gain,
        lane.volume / 100,
        lane,
        clipStart,
        clipStart - start,
        length
      );
      source.start(clipStart - start, offset, length);
    }
    return offline.startRendering();
  }

  async function exportMix() {
    if (!lanes.length || exporting) return;
    setExporting(true);
    setExportError("");
    if (playing) {
      stopSources();
      setPlaying(false);
    }
    try {
      const timelineEnd = lanes.reduce(
        (max, lane) => Math.max(max, lane.start + lane.duration),
        0
      );
      const start = exportRange === "loop" ? Math.min(loopStart, loopEnd) : 0;
      const end = exportRange === "loop" ? Math.max(loopStart, loopEnd) : timelineEnd;
      const rendered = await renderMix({ start, end });
      const safeName = (sessionName || "camxora-mix").replace(/[\\/:*?"<>|]+/g, "-");
      const suffix = exportRange === "loop" ? "-loop" : "";
      if (exportFormat === "mp3") {
        saveBlob(await encodeMp3(rendered), `${safeName}${suffix}.mp3`);
      } else {
        saveBlob(encodeWav(rendered), `${safeName}${suffix}.wav`);
      }
    } catch (cause) {
      setExportError(cause instanceof Error ? cause.message : "Could not export the mix");
    } finally {
      setExporting(false);
    }
  }

  async function exportStems() {
    if (!lanes.length || exporting) return;
    setExporting(true);
    setExportError("");
    if (playing) {
      stopSources();
      setPlaying(false);
    }
    try {
      const sourceLanes = lanes.filter((lane) => !lane.muted && lane.duration > 0);
      if (!sourceLanes.length) throw new Error("Every track is muted.");
      const safeName = (sessionName || "camxora-mix").replace(/[\\/:*?"<>|]+/g, "-");
      const zip = new JSZip();
      for (const [index, lane] of sourceLanes.entries()) {
        const rendered = await renderMix({
          start: lane.start,
          end: lane.start + lane.duration,
          laneIds: new Set([lane.id]),
        });
        const safeTitle = (lane.title || "stem").replace(/[\\/:*?"<>|]+/g, "-");
        const prefix = String(index + 1).padStart(2, "0");
        if (exportFormat === "mp3") {
          zip.file(`${prefix}-${safeTitle}.mp3`, await encodeMp3(rendered));
        } else {
          zip.file(`${prefix}-${safeTitle}.wav`, encodeWav(rendered));
        }
      }
      const archive = await zip.generateAsync({ type: "blob", compression: "STORE" });
      saveBlob(archive, `${safeName}-stems.zip`);
    } catch (cause) {
      setExportError(cause instanceof Error ? cause.message : "Could not export stems");
    } finally {
      setExporting(false);
    }
  }

  function operationClipsToLanes(
    clips: NonNullable<StudioOperation["result"]>["clips"],
    source: Clip,
    prefix: string
  ): Clip[] {
    return (clips ?? []).map((clip, index): Clip => {
      const id = String(clip.id || makeId());
      const audioUrl =
        clip.durable_url ||
        clip.durableUrl ||
        (clip.audio_url && !clip.audio_url.includes("/forbidden")
          ? clip.audio_url
          : clip.media_urls?.find((media) => media.url)?.url || null);
      return {
        id: makeId(),
        generationId: source.generationId,
        variant: `edit-${id}`,
        title: clip.title || clip.label || `${prefix} ${index + 1}`,
        style: source.style,
        color: COLORS[(lanes.length + index) % COLORS.length],
        image: clip.image_url || source.image,
        start: source.start,
        duration: Math.max(12, Math.round(Number(clip.duration_seconds || clip.duration || source.duration))),
        offset: 0,
        fadeIn: 0,
        fadeOut: 0,
        audioUrl,
        low: 0,
        mid: 0,
        high: 0,
        delay: 0,
        reverb: 0,
        volume: 80,
        pan: 0,
        muted: false,
        solo: false,
      };
    });
  }

  async function runStudioEdit(
    label: string,
    request: () => Promise<StudioOperation>
  ) {
    if (!selectedLane || editBusy) return;
    if (selectedLane.variant !== "ok" && selectedLane.variant !== "alt") {
      setEditError("Select an original version before editing it.");
      return;
    }
    setEditBusy(true);
    setEditError("");
    setEditStatus(`Submitting ${label.toLowerCase()}…`);
    try {
      let operation = await request();
      for (let attempt = 0; attempt < 80; attempt += 1) {
        if (["complete", "success", "error", "failed"].includes(operation.status.toLowerCase())) {
          break;
        }
        await new Promise((resolve) => window.setTimeout(resolve, 3000));
        operation = await getStudioOperation(operation.id);
        setEditStatus(`${label} in progress…`);
      }
      if (["error", "failed"].includes(operation.status.toLowerCase())) {
        throw new Error(operation.error_message || `${label} failed.`);
      }
      const next = operationClipsToLanes(operation.result?.clips, selectedLane, label);
      if (!next.length) throw new Error(`${label} returned no clips.`);
      commitLanes([...lanes, ...next]);
      setSelected(next[0].id);
      setEditStatus(`${label} added to the timeline`);
    } catch (cause) {
      setEditError(cause instanceof Error ? cause.message : `Could not run ${label}.`);
      setEditStatus("");
    } finally {
      setEditBusy(false);
    }
  }

  async function separateStems(mode: "vocal" | "stems") {
    if (!selectedLane || stemsBusy) return;
    if (selectedLane.variant !== "ok" && selectedLane.variant !== "alt") {
      setStemsError("Select an original version before separating stems.");
      return;
    }
    setStemsBusy(true);
    setStemsError("");
    setStemsStatus("Submitting stems?");
    try {
      let operation = await requestStudioStems({
        taskId: selectedLane.generationId,
        variant: selectedLane.variant,
        mode,
        projectId,
      });
      setStemsStatus(operation.status === "complete" ? "Stems ready" : "Separating stems?");
      for (let attempt = 0; attempt < 80; attempt += 1) {
        if (["complete", "success", "error", "failed"].includes(operation.status.toLowerCase())) break;
        await new Promise((resolve) => window.setTimeout(resolve, 3000));
        operation = await getStudioOperation(operation.id);
        setStemsStatus(operation.status === "complete" ? "Stems ready" : "Separating stems?");
      }
      if (["error", "failed"].includes(operation.status.toLowerCase())) {
        throw new Error(operation.error_message || "Stem separation failed.");
      }
      const clips = operation.result?.clips ?? [];
      if (!clips.length) throw new Error("Stem separation returned no clips.");
      // Suno returns two takes for each stem. One take is enough for a usable
      // session; otherwise a 12-track job would add 24 lanes at once.
      const seenStemNames = new Set<string>();
      const selectedClips = clips.filter((clip) => {
        const name = String(clip.title || clip.label || clip.id || "").trim().toLowerCase();
        if (!name) return true;
        if (seenStemNames.has(name)) return false;
        seenStemNames.add(name);
        return true;
      });
      const next = selectedClips.map((clip, index): Clip => {
        const id = String(clip.id || makeId());
        return {
          id: makeId(),
          generationId: selectedLane.generationId,
          variant: `stem-${id}`,
          title: clip.title || clip.label || `${mode === "vocal" ? "Stem" : "Stem"} ${index + 1}`,
          style: selectedLane.style,
          color: COLORS[(lanes.length + index) % COLORS.length],
          image: clip.image_url || selectedLane.image,
          start: selectedLane.start,
          duration: Math.max(12, Math.round(Number(clip.duration_seconds || clip.duration || selectedLane.duration))),
          offset: 0,
          fadeIn: 0,
          fadeOut: 0,
          audioUrl:
            clip.durable_url ||
            clip.durableUrl ||
            (clip.audio_url && !clip.audio_url.includes("/forbidden")
              ? clip.audio_url
              : clip.media_urls?.find((media) => media.url)?.url || null),
          low: 0,
          mid: 0,
          high: 0,
          delay: 0,
          reverb: 0,
          volume: 80,
          pan: 0,
          muted: false,
          solo: false,
        };
      });
      commitLanes([...lanes, ...next]);
      setSelected(next[0].id);
      setStemsStatus(
        clips.length > selectedClips.length
          ? `Stems added — ${selectedClips.length} lanes, one take`
          : "Stems added to the timeline"
      );
    } catch (cause) {
      setStemsError(cause instanceof Error ? cause.message : "Could not separate stems.");
      setStemsStatus("");
    } finally {
      setStemsBusy(false);
    }
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
            {cloudState === "saving" ? "Saving..." : cloudState === "error" ? "Saved locally - cloud offline" : cloudState === "saved" ? "Saved to cloud" : savedAt ? "Saved locally" : "Local session"} - {lanes.length}{" "}
            {lanes.length === 1 ? "track" : "tracks"}
            {totalMinutes > 0 ? ` - ${totalMinutes}m arrangement` : ""}
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
              setProjectId(null);
              setCloudState("local");
              setSessionName("Untitled session");
            }}
          >
            New session
          </button>
          <Link className="btn btn-ghost" href="/create">Create a track</Link>
          <div className="studio-export-group">
            <select
              className="studio-export-format"
              value={exportRange}
              onChange={(event) => setExportRange(event.target.value as "full" | "loop")}
              aria-label="Export range"
              disabled={exporting}
            >
              <option value="full">Full mix</option>
              <option value="loop">Loop range</option>
            </select>
            <select
              className="studio-export-format"
              value={exportFormat}
              onChange={(event) => setExportFormat(event.target.value as "wav" | "mp3")}
              aria-label="Export format"
              disabled={exporting}
            >
              <option value="wav">WAV</option>
              <option value="mp3">MP3 192k</option>
            </select>
            <button
              className="btn btn-ghost"
              type="button"
              disabled={!lanes.length || exporting}
              onClick={() => void exportStems()}
              title="Export each unmuted track into one ZIP archive"
            >
              <Icon name="fa-layer-group" /> {exporting ? "Rendering?" : "Stems ZIP"}
            </button>
            <button
              className="btn btn-primary"
              type="button"
              disabled={!lanes.length || exporting}
              onClick={() => void exportMix()}
              title={`Export a stereo ${exportFormat.toUpperCase()} mixdown`}
            >
              <Icon name={exporting ? "fa-spinner" : "fa-download"} />{" "}
              {exporting ? "Rendering?" : `Export ${exportFormat.toUpperCase()}`}
            </button>
          </div>
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
        <span className="studio-loop-range">
          <span>Loop</span>
          <input
            type="number"
            min={0}
            max={Math.max(0, loopEnd - 5)}
            step={1}
            value={Math.round(loopStart)}
            onChange={(event) => setLoopStart(clamp(Number(event.target.value), 0, loopEnd - 5))}
            aria-label="Loop start in seconds"
          />
          <em>-</em>
          <input
            type="number"
            min={loopStart + 5}
            max={timelineDuration}
            step={1}
            value={Math.round(loopEnd)}
            onChange={(event) => setLoopEnd(clamp(Number(event.target.value), loopStart + 5, timelineDuration))}
            aria-label="Loop end in seconds"
          />
        </span>
        <span className="studio-toolbar-spacer" />
        <span className="studio-time">{formatTime(playhead)} / {formatTime(timelineDuration)}</span>
      </div>

      <div className="studio-work">
        <aside className="studio-library">
          <div className="sec-head"><h2>Library</h2><Link href="/library">All</Link></div>
          <label className="studio-library-search">
            <Icon name="fa-magnifying-glass" />
            <input
              value={search}
              onChange={(event) => setSearch(event.target.value)}
              placeholder="Search library"
              aria-label="Search library"
            />
          </label>
          {!items.length ? (
            <div className="studio-library-empty">
              <Icon name="fa-music" />
              <p>No generated tracks yet.</p>
              <Link className="btn btn-ghost" href="/create">Create one</Link>
            </div>
          ) : !filteredItems.length ? (
            <div className="studio-library-empty">
              <Icon name="fa-magnifying-glass" />
              <p>No tracks match ?{search}?.</p>
            </div>
          ) : (
            <div className="studio-library-list">
              {filteredItems.map((item) => {
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
              <div
                className={`studio-loop-bar${loop ? " on" : ""}`}
                style={{
                  left: `${(loopStart / timelineDuration) * 100}%`,
                  width: `${((loopEnd - loopStart) / timelineDuration) * 100}%`,
                }}
                onPointerDown={(event) => event.stopPropagation()}
              >
                <span
                  className="studio-loop-handle start"
                  onPointerDown={(event) => beginLoopDrag(event, "start")}
                  title="Drag loop start"
                />
                <span
                  className="studio-loop-handle end"
                  onPointerDown={(event) => beginLoopDrag(event, "end")}
                  title="Drag loop end"
                />
              </div>
              {ticks.map((tick) => (
                <span key={tick} style={{ left: `${(tick / timelineDuration) * 100}%` }}>
                  {formatTime(tick)}
                </span>
              ))}
            </div>
            <span />
          </div>
          <div className="studio-lanes" style={{ zoom } as CSSProperties}>
            <div className="studio-loop-layer" aria-hidden="true">
              <span />
              <div className="studio-loop-layer-track">
                <i
                  style={{
                    left: `${(loopStart / timelineDuration) * 100}%`,
                    width: `${((loopEnd - loopStart) / timelineDuration) * 100}%`,
                  }}
                />
              </div>
              <span />
            </div>
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
                    {lane.fadeIn > 0 ? (
                      <span className="studio-clip-fade left" style={{ width: `${Math.min(50, (lane.fadeIn / lane.duration) * 100)}%` }} />
                    ) : null}
                    {lane.fadeOut > 0 ? (
                      <span className="studio-clip-fade right" style={{ width: `${Math.min(50, (lane.fadeOut / lane.duration) * 100)}%` }} />
                    ) : null}
                    <span className="studio-waveform" aria-hidden="true">
                      {waveformPeaks(
                        lane,
                        audioMeta[`${lane.generationId}:${lane.variant}`],
                        index
                      ).map((peak, bar) => (
                        <i key={bar} style={{ height: `${Math.max(8, peak * 100)}%` }} />
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
                <label>Fade in
                  <input type="number" min={0} max={10} step={0.1} value={Number(selectedLane.fadeIn.toFixed(1))} onChange={(event) => updateLane(selectedLane.id, { fadeIn: clamp(Number(event.target.value), 0, 10) })} />
                </label>
                <label>Fade out
                  <input type="number" min={0} max={10} step={0.1} value={Number(selectedLane.fadeOut.toFixed(1))} onChange={(event) => updateLane(selectedLane.id, { fadeOut: clamp(Number(event.target.value), 0, 10) })} />
                </label>
              </div>
              <label className="studio-slider">Volume <b>{selectedLane.volume}%</b>
                <input type="range" min="0" max="100" value={selectedLane.volume} onChange={(event) => updateLane(selectedLane.id, { volume: Number(event.target.value) })} />
              </label>
              <label className="studio-slider">Pan <b>{selectedLane.pan === 0 ? "C" : selectedLane.pan > 0 ? `R${selectedLane.pan}` : `L${Math.abs(selectedLane.pan)}`}</b>
                <input type="range" min="-50" max="50" value={selectedLane.pan} onChange={(event) => updateLane(selectedLane.id, { pan: Number(event.target.value) })} />
              </label>
              <div className="studio-eq">
                <div className="studio-eq-head">
                  <span>3-band EQ</span>
                  <button type="button" onClick={() => updateLane(selectedLane.id, { low: 0, mid: 0, high: 0 })}>Reset</button>
                </div>
                <label>Low <b>{selectedLane.low > 0 ? "+" : ""}{selectedLane.low} dB</b>
                  <input type="range" min="-12" max="12" step="0.5" value={selectedLane.low} onChange={(event) => updateLane(selectedLane.id, { low: Number(event.target.value) })} />
                </label>
                <label>Mid <b>{selectedLane.mid > 0 ? "+" : ""}{selectedLane.mid} dB</b>
                  <input type="range" min="-12" max="12" step="0.5" value={selectedLane.mid} onChange={(event) => updateLane(selectedLane.id, { mid: Number(event.target.value) })} />
                </label>
                <label>High <b>{selectedLane.high > 0 ? "+" : ""}{selectedLane.high} dB</b>
                  <input type="range" min="-12" max="12" step="0.5" value={selectedLane.high} onChange={(event) => updateLane(selectedLane.id, { high: Number(event.target.value) })} />
                </label>
              </div>
              <div className="studio-eq">
                <div className="studio-eq-head">
                  <span>FX sends</span>
                  <button type="button" onClick={() => updateLane(selectedLane.id, { delay: 0, reverb: 0 })}>Reset</button>
                </div>
                <label>Delay <b>{selectedLane.delay}%</b>
                  <input type="range" min="0" max="100" step="1" value={selectedLane.delay} onChange={(event) => updateLane(selectedLane.id, { delay: Number(event.target.value) })} />
                </label>
                <label>Reverb <b>{selectedLane.reverb}%</b>
                  <input type="range" min="0" max="100" step="1" value={selectedLane.reverb} onChange={(event) => updateLane(selectedLane.id, { reverb: Number(event.target.value) })} />
                </label>
              </div>
              <div className="studio-inspector-actions">
                <button className={selectedLane.muted ? "on" : ""} type="button" onClick={() => updateLane(selectedLane.id, { muted: !selectedLane.muted })}>Mute</button>
                <button className={selectedLane.solo ? "on" : ""} type="button" onClick={() => updateLane(selectedLane.id, { solo: !selectedLane.solo })}>Solo</button>
              </div>
              <div className="studio-inspector-actions">
                <button type="button" onClick={splitSelected} disabled={!canSplit}>Split</button>
                <button type="button" onClick={duplicateSelected}>Duplicate</button>
              </div>
              <div className="studio-stem-actions">
                <span>Separate stems</span>
                <div>
                  <button type="button" onClick={() => void separateStems("vocal")} disabled={stemsBusy || (selectedLane.variant !== "ok" && selectedLane.variant !== "alt")}>
                    <Icon name="fa-user" /> Vocals + instrumental
                    {studioPricing ? <em>· {studioPricing.stems_2} cr</em> : null}
                  </button>
                  <button type="button" onClick={() => void separateStems("stems")} disabled={stemsBusy || (selectedLane.variant !== "ok" && selectedLane.variant !== "alt")}>
                    <Icon name="fa-layer-group" /> Full stems
                    {studioPricing ? <em>· {studioPricing.stems_12} cr</em> : null}
                  </button>
                </div>
                {stemsStatus ? <small>{stemsStatus}</small> : null}
                {stemsError ? <small className="studio-stem-error">{stemsError}</small> : null}
              </div>
              <div className="studio-edit-actions">
                <span>
                  AI edits
                  {studioPricing ? <em> · {studioPricing.edit} cr each</em> : null}
                </span>
                <input
                  value={editPrompt}
                  onChange={(event) => setEditPrompt(event.target.value)}
                  placeholder="Describe a cover or vocal change…"
                  maxLength={500}
                />
                <div>
                  <button
                    type="button"
                    onClick={() =>
                      void runStudioEdit("Extend", () =>
                        requestStudioExtend({
                          taskId: selectedLane.generationId,
                          variant: selectedLane.variant,
                          continueAt: Math.round(selectedLane.start + selectedLane.duration),
                          projectId,
                        })
                      )
                    }
                    disabled={editBusy || stemsBusy || (selectedLane.variant !== "ok" && selectedLane.variant !== "alt")}
                  >
                    <Icon name="fa-arrow-right-long" /> Extend
                  </button>
                  <button
                    type="button"
                    onClick={() =>
                      void runStudioEdit("Cover", () =>
                        requestStudioCover({
                          taskId: selectedLane.generationId,
                          variant: selectedLane.variant,
                          prompt: editPrompt.trim() || selectedLane.style,
                          projectId,
                        })
                      )
                    }
                    disabled={editBusy || stemsBusy || (selectedLane.variant !== "ok" && selectedLane.variant !== "alt")}
                  >
                    <Icon name="fa-repeat" /> Cover
                  </button>
                  <button
                    type="button"
                    onClick={() =>
                      void runStudioEdit("Add vocals", () =>
                        requestStudioAddVocals({
                          taskId: selectedLane.generationId,
                          variant: selectedLane.variant,
                          prompt: editPrompt.trim(),
                          projectId,
                        })
                      )
                    }
                    disabled={editBusy || stemsBusy || !editPrompt.trim() || (selectedLane.variant !== "ok" && selectedLane.variant !== "alt")}
                  >
                    <Icon name="fa-microphone" /> Add vocals
                  </button>
                  <button
                    type="button"
                    onClick={() =>
                      void runStudioEdit("Add instrumental", () =>
                        requestStudioAddInstrumental({
                          taskId: selectedLane.generationId,
                          variant: selectedLane.variant,
                          prompt: editPrompt.trim(),
                          projectId,
                        })
                      )
                    }
                    disabled={editBusy || stemsBusy || !editPrompt.trim() || (selectedLane.variant !== "ok" && selectedLane.variant !== "alt")}
                  >
                    <Icon name="fa-guitar" /> Add instrumental
                  </button>
                </div>
                <textarea
                  value={replaceLyrics}
                  onChange={(event) => setReplaceLyrics(event.target.value)}
                  placeholder="Replacement lyrics for the selected range…"
                  maxLength={5000}
                  rows={3}
                />
                <button
                  className="studio-edit-replace"
                  type="button"
                  onClick={() =>
                    void runStudioEdit("Replace section", () =>
                      requestStudioReplaceSection({
                        taskId: selectedLane.generationId,
                        variant: selectedLane.variant,
                        startS: loop ? loopStart : selectedLane.start,
                        endS: loop ? loopEnd : selectedLane.start + selectedLane.duration,
                        lyrics: replaceLyrics.trim(),
                        prompt: editPrompt.trim(),
                        projectId,
                      })
                    )
                  }
                  disabled={
                    editBusy ||
                    stemsBusy ||
                    !replaceLyrics.trim() ||
                    (selectedLane.variant !== "ok" && selectedLane.variant !== "alt") ||
                    (loop && loopEnd <= loopStart)
                  }
                >
                  <Icon name="fa-scissors" /> Replace {loop ? `${Math.round(loopStart)}–${Math.round(loopEnd)}s` : "full clip"}
                </button>
                {editStatus ? <small>{editStatus}</small> : null}
                {editError ? <small className="studio-stem-error">{editError}</small> : null}
              </div>
              <button className="studio-inspector-delete" type="button" onClick={deleteSelected}>
                <Icon name="fa-trash" /> Remove from session
              </button>
              <div className="studio-inspector-note">
                <Icon name="fa-circle-info" /> Preview mix. Export creates a stereo WAV or MP3 mixdown.
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
          <button
            className={`studio-loop-btn${loop ? " on" : ""}`}
            type="button"
            aria-label="Loop arrangement"
            aria-pressed={loop}
            title="Loop arrangement"
            disabled={!lanes.length}
            onClick={() => setLoop((value) => !value)}
          >
            <Icon name="fa-repeat" />
          </button>
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
      {exportError ? <p className="studio-audio-error" role="alert">{exportError}</p> : null}
      {cloudError ? <p className="studio-audio-error" role="alert">{cloudError}</p> : null}
      {audioLoading ? <p className="studio-audio-status" role="status">Loading studio audio?</p> : null}
      {exporting ? <p className="studio-audio-status" role="status">Rendering mixdown?</p> : null}
    </div>
  );
}
