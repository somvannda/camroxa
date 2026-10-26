"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
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
  uploadStudioAudio,
  getStudioUploadUrl,
  listStudioProjectVersions,
  createStudioProjectVersion,
  restoreStudioProjectVersion,
  type StudioProjectVersion,
  type StudioShareComment,
  createStudioProjectShare,
  listStudioProjectComments,
  getStudioSharedProject,
  updateStudioSharedProject,
  deleteStudioProject,
  touchStudioPresence,
  type StudioPresence,
} from "@/lib/studio-api";

type AutomationPoint = {
  id: string;
  time: number;
  value: number;
};

type MidiNote = {
  id: string;
  time: number;
  pitch: number;
  duration: number;
  velocity: number;
};

type TimelineMarker = {
  id: string;
  time: number;
  label: string;
  color: string;
};

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
  automation?: AutomationPoint[];
  panAutomation?: AutomationPoint[];
  audioUrl?: string | null;
  uploadId?: string | null;
  midiNotes?: MidiNote[];
  instrument?: "sine" | "triangle" | "sawtooth";
  low: number;
  mid: number;
  high: number;
  delay: number;
  reverb: number;
  chorus: number;
  compressor: number;
  drive: number;
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
  timeSignature?: string;
  gridDivision?: "off" | "bar" | "beat" | "1/8" | "1/16";
  zoom?: number;
  master?: number;
  loopStart?: number;
  loopEnd?: number;
  markers?: TimelineMarker[];
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
  const automation = (lane.automation ?? [])
    .filter((point) => point.time <= elapsed + length)
    .sort((a, b) => a.time - b.time);
  if (automation.length) {
    const prior = [...automation].reverse().find((point) => point.time <= elapsed);
    const first = prior ?? automation[0];
    gain.gain.setValueAtTime(base * (first.value / 100), when);
    for (const point of automation) {
      if (point.time <= elapsed) continue;
      const at = when + (point.time - elapsed);
      gain.gain.linearRampToValueAtTime(base * (point.value / 100), Math.max(when + 0.001, at));
    }
    return;
  }
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

function schedulePanAutomation(
  panner: StereoPannerNode,
  lane: Clip,
  from: number,
  when: number,
  length: number
) {
  const elapsed = Math.max(0, from - lane.start);
  const points = (lane.panAutomation ?? [])
    .filter((point) => point.time <= elapsed + length)
    .sort((a, b) => a.time - b.time);
  if (!points.length) return;
  const prior = [...points].reverse().find((point) => point.time <= elapsed);
  const first = prior ?? points[0];
  panner.pan.setValueAtTime(clamp(first.value / 50, -1, 1), when);
  for (const point of points) {
    if (point.time <= elapsed) continue;
    panner.pan.linearRampToValueAtTime(
      clamp(point.value / 50, -1, 1),
      Math.max(when + 0.001, when + (point.time - elapsed))
    );
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

function connectTrackDrive(
  context: BaseAudioContext,
  input: AudioNode,
  output: AudioNode,
  lane: Clip
) {
  const amount = clamp(lane.drive / 100, 0, 1);
  if (amount <= 0) {
    input.connect(output);
    return;
  }
  const shaper = context.createWaveShaper();
  const samples = 1024;
  const curve = new Float32Array(samples);
  const drive = 1 + amount * 24;
  for (let index = 0; index < samples; index += 1) {
    const x = (index / (samples - 1)) * 2 - 1;
    curve[index] = Math.tanh(x * drive);
  }
  shaper.curve = curve;
  shaper.oversample = "4x";
  input.connect(shaper);
  shaper.connect(output);
}

function connectTrackChorus(
  context: BaseAudioContext,
  input: AudioNode,
  output: AudioNode,
  lane: Clip,
  when: number,
  length: number
) {
  const amount = clamp(lane.chorus / 100, 0, 1);
  if (amount <= 0) {
    input.connect(output);
    return;
  }
  const dry = context.createGain();
  dry.gain.value = 1;
  const wet = context.createGain();
  wet.gain.value = amount * 0.45;
  const delay = context.createDelay(0.08);
  delay.delayTime.value = 0.024;
  const lfo = context.createOscillator();
  lfo.frequency.value = 0.35 + amount * 0.55;
  const depth = context.createGain();
  depth.gain.value = 0.002 + amount * 0.006;
  lfo.connect(depth);
  depth.connect(delay.delayTime);
  input.connect(dry);
  dry.connect(output);
  input.connect(delay);
  delay.connect(wet);
  wet.connect(output);
  lfo.start(when);
  lfo.stop(when + Math.max(0.1, length) + 0.1);
}

function connectTrackDynamics(
  context: BaseAudioContext,
  input: AudioNode,
  output: AudioNode,
  lane: Clip
) {
  const amount = clamp(lane.compressor / 100, 0, 1);
  const compressor = context.createDynamicsCompressor();
  compressor.threshold.value = -6 - amount * 24;
  compressor.knee.value = 6;
  compressor.ratio.value = 1 + amount * 11;
  compressor.attack.value = 0.003;
  compressor.release.value = 0.1;
  input.connect(compressor);
  compressor.connect(output);
}

async function renderMidiBuffer(
  notes: MidiNote[],
  duration: number,
  instrument: Clip["instrument"]
): Promise<AudioBuffer> {
  const sampleRate = 44100;
  const offline = new OfflineAudioContext(
    2,
    Math.max(1, Math.ceil(Math.max(0.1, duration) * sampleRate)),
    sampleRate
  );
  for (const note of notes) {
    const start = Math.max(0, note.time);
    const length = Math.max(0.05, note.duration);
    if (start >= duration) continue;
    const osc = offline.createOscillator();
    osc.type = instrument || "triangle";
    osc.frequency.value = 440 * Math.pow(2, (note.pitch - 69) / 12);
    const gain = offline.createGain();
    const velocity = clamp(note.velocity, 0, 1);
    const attack = 0.01;
    const release = 0.08;
    gain.gain.setValueAtTime(0, start);
    gain.gain.linearRampToValueAtTime(velocity, start + attack);
    gain.gain.setValueAtTime(velocity, start + Math.max(attack, length));
    gain.gain.linearRampToValueAtTime(0, start + length + release);
    osc.connect(gain);
    gain.connect(offline.destination);
    osc.start(start);
    osc.stop(Math.min(duration, start + length + release));
  }
  return offline.startRendering();
}

function midiNoteName(pitch: number): string {
  const names = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"];
  return `${names[((pitch % 12) + 12) % 12]}${Math.floor(pitch / 12) - 1}`;
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
    automation: [],
    panAutomation: [],
    audioUrl: null,
    low: 0,
    mid: 0,
    high: 0,
    delay: 0,
    reverb: 0,
    chorus: 0,
    compressor: 0,
    drive: 0,
    volume: 80,
    pan: 0,
    muted: false,
    solo: false,
  };
}

export function StudioEditorView() {
  const { user, loading: authLoading } = useAuth();
  const searchParams = useSearchParams();
  const shareParam = searchParams.get("share");
  const { playing: mainPlaying, togglePlay: toggleMainPlayer } = usePlayer();
  const [items, setItems] = useState<WebMusicGeneration[]>([]);
  const [lanes, setLanes] = useState<Clip[]>([]);
  const [audioMeta, setAudioMeta] = useState<Record<string, AudioMeta>>({});
  const [search, setSearch] = useState("");
  const [libraryFilter, setLibraryFilter] = useState<"all" | "instrumental" | "vocal" | "ready">("all");
  const [selected, setSelected] = useState<string | null>(null);
  const [sessionName, setSessionName] = useState("Untitled session");
  const [bpm, setBpm] = useState(90);
  const [timeSignature, setTimeSignature] = useState("4/4");
  const [gridDivision, setGridDivision] = useState<"off" | "bar" | "beat" | "1/8" | "1/16">("beat");
  const [zoom, setZoom] = useState(1);
  const [master, setMaster] = useState(80);
  const [playhead, setPlayhead] = useState(0);
  const [playing, setPlaying] = useState(false);
  const [audioLoading, setAudioLoading] = useState(false);
  const [audioError, setAudioError] = useState("");
  const [exporting, setExporting] = useState(false);
  const [exportError, setExportError] = useState("");
  const [importing, setImporting] = useState(false);
  const [importError, setImportError] = useState("");
  const [recording, setRecording] = useState(false);
  const [recordSeconds, setRecordSeconds] = useState(0);
  const [recordError, setRecordError] = useState("");
  const [exportFormat, setExportFormat] = useState<"wav" | "mp3">("wav");
  const [exportRange, setExportRange] = useState<"full" | "loop">("full");
  const [loop, setLoop] = useState(false);
  const [loopStart, setLoopStart] = useState(0);
  const [loopEnd, setLoopEnd] = useState(60);
  const [markers, setMarkers] = useState<TimelineMarker[]>([]);
  const [metronome, setMetronome] = useState(false);
  const [loaded, setLoaded] = useState(false);
  const [savedAt, setSavedAt] = useState<Date | null>(null);
  const [projectId, setProjectId] = useState<string | null>(null);
  const [cloudState, setCloudState] = useState<"local" | "saving" | "saved" | "error">("local");
  const [cloudError, setCloudError] = useState("");
  const [projectsOpen, setProjectsOpen] = useState(false);
  const [projectList, setProjectList] = useState<Array<{ id: string; title: string; updated_at?: string | null }>>([]);
  const [projectsBusy, setProjectsBusy] = useState(false);
  const [projectsError, setProjectsError] = useState("");
  const [versionsOpen, setVersionsOpen] = useState(false);
  const [versions, setVersions] = useState<StudioProjectVersion[]>([]);
  const [versionsBusy, setVersionsBusy] = useState(false);
  const [versionsError, setVersionsError] = useState("");
  const [versionLabel, setVersionLabel] = useState("");
  const [shareOpen, setShareOpen] = useState(false);
  const [shareUrl, setShareUrl] = useState("");
  const [shareBusy, setShareBusy] = useState(false);
  const [shareError, setShareError] = useState("");
  const [projectComments, setProjectComments] = useState<StudioShareComment[]>([]);
  const [commentsBusy, setCommentsBusy] = useState(false);
  const [commentsError, setCommentsError] = useState("");
  const [sharePermission, setSharePermission] = useState<"view" | "edit">("view");
  const [sharedToken, setSharedToken] = useState<string | null>(null);
  const [collaborators, setCollaborators] = useState<StudioPresence[]>([]);
  const [remoteChanges, setRemoteChanges] = useState(false);
  const sharedUpdatedAtRef = useRef("");
  const sharedHydratingRef = useRef(false);
  const [actionsOpen, setActionsOpen] = useState(false);
  const [libraryOpen, setLibraryOpen] = useState(true);
  const [inspectorOpen, setInspectorOpen] = useState(true);
  const [aiPrompt, setAiPrompt] = useState("");
  const [aiStatus, setAiStatus] = useState("");
  const [clipMenu, setClipMenu] = useState<{ x: number; y: number; laneId: string } | null>(null);
  const [inspectorTab, setInspectorTab] = useState<"clip" | "mix" | "ai">("clip");
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
  const metronomeRef = useRef(false);
  const loopDragRef = useRef<{ which: "start" | "end"; startX: number; start: number; end: number; width: number } | null>(null);
  const startPlaybackRef = useRef<(from: number) => Promise<void>>(async () => {});
  const playheadRef = useRef(0);
  const timelineDurationRef = useRef(180);
  const audioCtxRef = useRef<AudioContext | null>(null);
  const masterGainRef = useRef<GainNode | null>(null);
  const buffersRef = useRef<Map<string, AudioBuffer>>(new Map());
  const sourcesRef = useRef<AudioScheduledSourceNode[]>([]);
  const nodesRef = useRef<Map<string, { gain: GainNode; panner: StereoPannerNode; low: BiquadFilterNode; mid: BiquadFilterNode; high: BiquadFilterNode; delayWet: GainNode; reverbWet: GainNode }>>(new Map());
  const startedAtRef = useRef(0);
  const startPlayheadRef = useRef(0);
  const rafRef = useRef<number | null>(null);
  const recorderRef = useRef<MediaRecorder | null>(null);
  const recordStreamRef = useRef<MediaStream | null>(null);
  const recordChunksRef = useRef<Blob[]>([]);
  const recordTimerRef = useRef<number | null>(null);

  const storageKey = user ? `${STORAGE_PREFIX}:${user.id}` : "";
  const cloudSaveRef = useRef(false);

  useEffect(() => {
    playheadRef.current = playhead;
  }, [playhead]);

  useEffect(() => {
    loopRef.current = loop;
  }, [loop]);

  useEffect(() => {
    metronomeRef.current = metronome;
  }, [metronome]);

  useEffect(() => {
    setInspectorTab("clip");
  }, [selected]);

  useEffect(() => {
    if (!clipMenu) return;
    const close = (event: PointerEvent) => {
      const target = event.target;
      if (target instanceof Element && target.closest(".studio-clip-menu")) return;
      setClipMenu(null);
    };
    const key = (event: KeyboardEvent) => {
      if (event.key === "Escape") setClipMenu(null);
    };
    document.addEventListener("pointerdown", close);
    document.addEventListener("keydown", key);
    return () => {
      document.removeEventListener("pointerdown", close);
      document.removeEventListener("keydown", key);
    };
  }, [clipMenu]);

  useEffect(() => {
    if (!actionsOpen) return;
    const onPointerDown = (event: PointerEvent) => {
      const target = event.target;
      if (target instanceof Element && target.closest(".studio-actions-menu-wrap")) return;
      setActionsOpen(false);
    };
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") setActionsOpen(false);
    };
    document.addEventListener("pointerdown", onPointerDown);
    document.addEventListener("keydown", onKeyDown);
    return () => {
      document.removeEventListener("pointerdown", onPointerDown);
      document.removeEventListener("keydown", onKeyDown);
    };
  }, [actionsOpen]);

  useEffect(() => {
    loopStartRef.current = loopStart;
    loopEndRef.current = loopEnd;
  }, [loopStart, loopEnd]);

  useEffect(() => {
    return () => {
      if (recordTimerRef.current !== null) window.clearInterval(recordTimerRef.current);
      recordStreamRef.current?.getTracks().forEach((track) => track.stop());
      recorderRef.current = null;
    };
  }, []);

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
        chorus: Number.isFinite(lane.chorus) ? clamp(Number(lane.chorus), 0, 100) : 0,
        compressor: Number.isFinite(lane.compressor) ? clamp(Number(lane.compressor), 0, 100) : 0,
        drive: Number.isFinite(lane.drive) ? clamp(Number(lane.drive), 0, 100) : 0,
        automation: Array.isArray(lane.automation)
          ? lane.automation
              .filter(
                (point): point is AutomationPoint =>
                  Boolean(point) &&
                  Number.isFinite((point as AutomationPoint).time) &&
                  Number.isFinite((point as AutomationPoint).value)
              )
              .map((point) => ({
                id: String(point.id || makeId()),
                time: clamp(Number(point.time), 0, lane.duration),
                value: clamp(Number(point.value), 0, 100),
              }))
              .sort((a, b) => a.time - b.time)
          : [],
        panAutomation: Array.isArray(lane.panAutomation)
          ? lane.panAutomation
              .filter(
                (point): point is AutomationPoint =>
                  Boolean(point) &&
                  Number.isFinite((point as AutomationPoint).time) &&
                  Number.isFinite((point as AutomationPoint).value)
              )
              .map((point) => ({
                id: String(point.id || makeId()),
                time: clamp(Number(point.time), 0, lane.duration),
                value: clamp(Number(point.value), -50, 50),
              }))
              .sort((a, b) => a.time - b.time)
          : [],
      }));
  }

  function applySession(saved: StoredSession, nextProjectId: string | null) {
    const savedLanes = normalizeLanes(saved.lanes);
    setLanes(savedLanes);
    setSelected(savedLanes[0]?.id ?? null);
    if (saved.name) setSessionName(saved.name);
    if (Number.isFinite(saved.bpm)) setBpm(clamp(Number(saved.bpm), 40, 220));
    if (["4/4", "3/4", "6/8"].includes(String(saved.timeSignature))) {
      setTimeSignature(String(saved.timeSignature));
    }
    if (["off", "bar", "beat", "1/8", "1/16"].includes(String(saved.gridDivision))) {
      setGridDivision(String(saved.gridDivision) as typeof gridDivision);
    }
    if (Number.isFinite(saved.zoom)) setZoom(clamp(Number(saved.zoom), 0.7, 2));
    if (Number.isFinite(saved.master)) setMaster(clamp(Number(saved.master), 0, 100));
    if (Number.isFinite(saved.loopStart)) setLoopStart(Math.max(0, Number(saved.loopStart)));
    if (Number.isFinite(saved.loopEnd)) setLoopEnd(Math.max(1, Number(saved.loopEnd)));
    setMarkers(
      Array.isArray(saved.markers)
        ? saved.markers
            .filter(
              (marker): marker is TimelineMarker =>
                Boolean(marker) &&
                Number.isFinite((marker as TimelineMarker).time) &&
                typeof (marker as TimelineMarker).label === "string"
            )
            .map((marker) => ({
              id: String(marker.id || makeId()),
              time: Math.max(0, Number(marker.time)),
              label: marker.label.slice(0, 80),
              color: marker.color || "#38bdf8",
            }))
            .sort((a, b) => a.time - b.time)
        : []
    );
    setProjectId(nextProjectId);
    setCloudState(nextProjectId ? "saved" : "local");
  }

  useEffect(() => {
    if (authLoading || !user) return;
    let active = true;
    setLoaded(false);
    if (shareParam) {
      getStudioSharedProject(shareParam)
        .then((project) => {
          if (!active) return;
          if (project.permission !== "edit") {
            setCloudError("This share link is view-only. Use the shared preview page instead.");
            setLoaded(true);
            return;
          }
          const data = (project.data || {}) as StudioProjectData;
          applySession(
            {
              name: project.title,
              bpm: project.bpm,
              timeSignature: project.time_signature,
              gridDivision: data.gridDivision as StoredSession["gridDivision"],
              zoom: Number.isFinite(data.zoom) ? Number(data.zoom) : 1,
              master: Number.isFinite(data.master) ? Number(data.master) : 80,
              loopStart: Number.isFinite(data.loopStart) ? Number(data.loopStart) : 0,
              loopEnd: Number.isFinite(data.loopEnd) ? Number(data.loopEnd) : 60,
              markers: data.markers as TimelineMarker[],
              lanes: normalizeLanes(data.lanes),
            },
            project.id
          );
          sharedUpdatedAtRef.current = project.updated_at || "";
          sharedHydratingRef.current = true;
          window.setTimeout(() => {
            sharedHydratingRef.current = false;
          }, 1000);
          setRemoteChanges(false);
          setSharedToken(shareParam);
          setLoaded(true);
        })
        .catch((cause) => {
          if (!active) return;
          setCloudError(cause instanceof Error ? cause.message : "Could not load shared project.");
          setLoaded(true);
        });
      return () => {
        active = false;
      };
    }
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
                timeSignature: project.time_signature,
                gridDivision: data.gridDivision as StoredSession["gridDivision"],
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
  }, [authLoading, user, storageKey, shareParam]);

  useEffect(() => {
    if (!loaded || !user || !storageKey) return;
    const timer = window.setTimeout(() => {
      const payload: StoredSession = { name: sessionName, bpm, timeSignature, gridDivision, zoom, master, loopStart, loopEnd, markers, lanes };
      window.localStorage.setItem(storageKey, JSON.stringify(payload));
      setSavedAt(new Date());
    }, 350);
    return () => window.clearTimeout(timer);
  }, [loaded, user, storageKey, sessionName, bpm, timeSignature, gridDivision, zoom, master, loopStart, loopEnd, markers, lanes]);

  useEffect(() => {
    if (!loaded || !user || cloudSaveRef.current) return;
    if (!lanes.length && sessionName === "Untitled session") return;
    const timer = window.setTimeout(async () => {
      if (sharedToken && sharedHydratingRef.current) return;
      if (cloudSaveRef.current) return;
      cloudSaveRef.current = true;
      setCloudState("saving");
      setCloudError("");
      try {
        const data: StudioProjectData = { lanes, gridDivision, loopStart, loopEnd, markers, zoom, master };
        if (sharedToken) {
          const saved = await updateStudioSharedProject(sharedToken, {
            title: sessionName,
            bpm,
            time_signature: timeSignature,
            data,
            expectedUpdatedAt: sharedUpdatedAtRef.current || null,
          });
          if (saved.updated_at) {
            sharedUpdatedAtRef.current = saved.updated_at;
          }
          setRemoteChanges(false);
        } else if (projectId) {
          await updateStudioProject(projectId, {
            title: sessionName,
            bpm,
            time_signature: timeSignature,
            data,
          });
        } else {
          const created = await createStudioProject({
            title: sessionName,
            major_version: 2,
            bpm,
            time_signature: timeSignature,
            data,
          });
          setProjectId(created.id);
        }
        setCloudState("saved");
        setSavedAt(new Date());
      } catch (cause) {
        const message = cause instanceof Error ? cause.message : "Cloud save failed";
        setCloudState("error");
        setCloudError(message);
        if (/changed since|conflict/i.test(message)) {
          setRemoteChanges(true);
        }
      } finally {
        cloudSaveRef.current = false;
      }
    }, 650);
    return () => window.clearTimeout(timer);
  }, [loaded, user, projectId, sharedToken, sessionName, bpm, timeSignature, gridDivision, zoom, master, loopStart, loopEnd, markers, lanes]);

  async function openProjects() {
    setProjectsOpen(true);
    setProjectsError("");
    setProjectsBusy(true);
    try {
      const result = await listStudioProjects(50, 0);
      setProjectList(result.items);
    } catch (cause) {
      setProjectsError(cause instanceof Error ? cause.message : "Could not load projects.");
    } finally {
      setProjectsBusy(false);
    }
  }

  async function openProject(projectIdToOpen: string) {
    setProjectsBusy(true);
    setProjectsError("");
    try {
      const project = await getStudioProject(projectIdToOpen);
      const data = (project.data || {}) as StudioProjectData;
      applySession(
        {
          name: project.title,
          bpm: project.bpm,
          timeSignature: project.time_signature,
          gridDivision: data.gridDivision as StoredSession["gridDivision"],
          zoom: Number.isFinite(data.zoom) ? Number(data.zoom) : 1,
          master: Number.isFinite(data.master) ? Number(data.master) : 80,
          loopStart: Number.isFinite(data.loopStart) ? Number(data.loopStart) : 0,
          loopEnd: Number.isFinite(data.loopEnd) ? Number(data.loopEnd) : 60,
          markers: data.markers as TimelineMarker[],
          lanes: normalizeLanes(data.lanes),
        },
        project.id
      );
      setSharedToken(null);
      setSessionName(project.title);
      setBpm(project.bpm);
      setTimeSignature(project.time_signature);
      setCloudState("saved");
      setProjectsOpen(false);
      setHistory([]);
      setFuture([]);
    } catch (cause) {
      setProjectsError(cause instanceof Error ? cause.message : "Could not open project.");
    } finally {
      setProjectsBusy(false);
    }
  }

  async function renameProject(project: { id: string; title: string }) {
    const next = window.prompt("Project name", project.title);
    if (next === null) return;
    const title = next.trim().slice(0, 120);
    if (!title) return;
    try {
      await updateStudioProject(project.id, { title });
      setProjectList((current) =>
        current.map((item) => (item.id === project.id ? { ...item, title } : item))
      );
      if (projectId === project.id) setSessionName(title);
    } catch (cause) {
      setProjectsError(cause instanceof Error ? cause.message : "Could not rename project.");
    }
  }

  async function deleteProject(project: { id: string; title: string }) {
    if (!window.confirm(`Delete \"${project.title}\"? This cannot be undone.`)) return;
    try {
      await deleteStudioProject(project.id);
      setProjectList((current) => current.filter((item) => item.id !== project.id));
      if (projectId === project.id) {
        commitLanes([]);
        setSelected(null);
        setProjectId(null);
        setSharedToken(null);
        setSessionName("Untitled session");
        setCloudState("local");
        setPlayhead(0);
      }
    } catch (cause) {
      setProjectsError(cause instanceof Error ? cause.message : "Could not delete project.");
    }
  }

  async function openVersions() {
    setVersionsOpen(true);
    setVersionsError("");
    if (!projectId) {
      setVersions([]);
      setVersionsError("Save the project to the cloud before creating versions.");
      return;
    }
    setVersionsBusy(true);
    try {
      const result = await listStudioProjectVersions(projectId);
      setVersions(result.items);
    } catch (cause) {
      setVersionsError(cause instanceof Error ? cause.message : "Could not load versions.");
    } finally {
      setVersionsBusy(false);
    }
  }

  function openShare() {
    setShareOpen(true);
    setShareError("");
    setCommentsError("");
    if (!projectId) {
      setProjectComments([]);
      return;
    }
    setCommentsBusy(true);
    void listStudioProjectComments(projectId)
      .then((result) => setProjectComments(result.items))
      .catch((cause) =>
        setCommentsError(cause instanceof Error ? cause.message : "Could not load comments.")
      )
      .finally(() => setCommentsBusy(false));
  }

  async function createShare() {
    if (!projectId || shareBusy) {
      if (!projectId) setShareError("Save the project to the cloud before sharing.");
      return;
    }
    setShareBusy(true);
    setShareError("");
    try {
      await updateStudioProject(projectId, {
        title: sessionName,
        bpm,
        time_signature: timeSignature,
        data: { lanes, gridDivision, loopStart, loopEnd, markers, zoom, master },
      });
      const share = await createStudioProjectShare(projectId, 7, sharePermission);
      setShareUrl(`${window.location.origin}${share.path}`);
    } catch (cause) {
      setShareError(cause instanceof Error ? cause.message : "Could not create share link.");
    } finally {
      setShareBusy(false);
    }
  }

  async function copyShare() {
    if (!shareUrl) return;
    try {
      await navigator.clipboard.writeText(shareUrl);
    } catch {
      /* Clipboard may be unavailable on plain HTTP. */
    }
  }

  async function saveVersion() {
    if (!projectId || versionsBusy) return;
    setVersionsBusy(true);
    setVersionsError("");
    try {
      await updateStudioProject(projectId, {
        title: sessionName,
        bpm,
        time_signature: timeSignature,
        data: { lanes, gridDivision, loopStart, loopEnd, markers, zoom, master },
      });
      const created = await createStudioProjectVersion(projectId, versionLabel.trim() || undefined);
      setVersions((current) => [created, ...current]);
      setVersionLabel("");
      setCloudState("saved");
    } catch (cause) {
      setVersionsError(cause instanceof Error ? cause.message : "Could not save version.");
    } finally {
      setVersionsBusy(false);
    }
  }

  async function restoreVersion(version: StudioProjectVersion) {
    if (!projectId || versionsBusy) return;
    if (!window.confirm(`Restore "${version.label || version.title}"? Current changes will be replaced.`)) {
      return;
    }
    setVersionsBusy(true);
    setVersionsError("");
    try {
      const project = await restoreStudioProjectVersion(projectId, version.id);
      applySession(project.data as StoredSession, project.id);
      setSessionName(project.title);
      setBpm(project.bpm);
      setTimeSignature(project.time_signature);
      setCloudState("saved");
      setVersionsOpen(false);
      setHistory([]);
      setFuture([]);
    } catch (cause) {
      setVersionsError(cause instanceof Error ? cause.message : "Could not restore version.");
    } finally {
      setVersionsBusy(false);
    }
  }

  useEffect(() => {
    if (!sharedToken || !user) return;
    let alive = true;
    const touch = () => {
      void touchStudioPresence(
        sharedToken,
        user.display_name || user.email || "Collaborator"
      )
        .then((result) => {
          if (alive) setCollaborators(result.items);
        })
        .catch(() => {
          /* presence is best-effort */
        });
    };
    touch();
    const timer = window.setInterval(touch, 20000);
    return () => {
      alive = false;
      window.clearInterval(timer);
    };
  }, [sharedToken, user]);

  async function reloadSharedProject() {
    if (!sharedToken) return;
    try {
      const project = await getStudioSharedProject(sharedToken);
      const data = (project.data || {}) as StudioProjectData;
      applySession(
        {
          name: project.title,
          bpm: project.bpm,
          timeSignature: project.time_signature,
          gridDivision: data.gridDivision as StoredSession["gridDivision"],
          zoom: Number.isFinite(data.zoom) ? Number(data.zoom) : 1,
          master: Number.isFinite(data.master) ? Number(data.master) : 80,
          loopStart: Number.isFinite(data.loopStart) ? Number(data.loopStart) : 0,
          loopEnd: Number.isFinite(data.loopEnd) ? Number(data.loopEnd) : 60,
          markers: data.markers as TimelineMarker[],
          lanes: normalizeLanes(data.lanes),
        },
        project.id
      );
      sharedUpdatedAtRef.current = project.updated_at || "";
      sharedHydratingRef.current = true;
      window.setTimeout(() => {
        sharedHydratingRef.current = false;
      }, 1000);
      setRemoteChanges(false);
    } catch {
      /* keep the current session if refresh fails */
    }
  }

  useEffect(() => {
    if (!sharedToken) return;
    const timer = window.setInterval(async () => {
      try {
        const project = await getStudioSharedProject(sharedToken);
        const remote = project.updated_at ? Date.parse(project.updated_at) || 0 : 0;
        const local = sharedUpdatedAtRef.current ? Date.parse(sharedUpdatedAtRef.current) || 0 : 0;
        if (remote > local + 750 && !cloudSaveRef.current) {
          setRemoteChanges(true);
        }
      } catch {
        /* polling is best-effort */
      }
    }, 5000);
    return () => window.clearInterval(timer);
  }, [sharedToken]);

  const timelineDuration = useMemo(() => {
    const end = lanes.reduce((max, lane) => Math.max(max, lane.start + lane.duration), 0);
    return Math.max(240, Math.ceil(Math.max(end, playhead + 10) / 30) * 30);
  }, [lanes, playhead]);

  useEffect(() => {
    timelineDurationRef.current = timelineDuration;
    setLoopEnd((current) => Math.min(current, timelineDuration));
    setLoopStart((current) => Math.min(current, Math.max(0, timelineDuration - 5)));
  }, [timelineDuration]);

  const barBeat = useMemo(() => {
    const [numerator, denominator] = timeSignature.split("/").map(Number);
    const beatsPerBar = Math.max(1, numerator || 4);
    const secondsPerBeat = (60 / Math.max(40, bpm)) * (4 / Math.max(1, denominator || 4));
    const secondsPerBar = secondsPerBeat * beatsPerBar;
    const bar = Math.floor(playhead / secondsPerBar) + 1;
    const beat = Math.floor((playhead % secondsPerBar) / secondsPerBeat) + 1;
    return `${String(bar).padStart(3, "0")}.${beat}.1`;
  }, [bpm, playhead, timeSignature]);

  const snapToGrid = useCallback(
    (value: number) => {
      if (gridDivision === "off") return value;
      const [numerator, denominator] = timeSignature.split("/").map(Number);
      const beat = (60 / Math.max(40, bpm)) * (4 / Math.max(1, denominator || 4));
      const bar = beat * Math.max(1, numerator || 4);
      const step =
        gridDivision === "bar"
          ? bar
          : gridDivision === "beat"
            ? beat
            : gridDivision === "1/8"
              ? beat / 2
              : beat / 4;
      return Math.round(value / step) * step;
    },
    [bpm, gridDivision, timeSignature]
  );

  const tickStep = timelineDuration > 300 ? 60 : 30;
  const ticks = useMemo(() => {
    const list: number[] = [];
    for (let time = 0; time <= timelineDuration; time += tickStep) list.push(time);
    return list;
  }, [timelineDuration, tickStep]);

  const filteredItems = useMemo(() => {
    const query = search.trim().toLowerCase();
    return items.filter((item) => {
      if (libraryFilter === "instrumental" && !item.instrumental) return false;
      if (libraryFilter === "vocal" && item.instrumental) return false;
      if (
        libraryFilter === "ready" &&
        !item.clips?.some((clip) => clip.ready || clip.audio_url)
      ) {
        return false;
      }
      if (!query) return true;
      return `${item.title} ${item.style || ""}`.toLowerCase().includes(query);
    });
  }, [items, libraryFilter, search]);

  const selectedLane = lanes.find((lane) => lane.id === selected) ?? null;
  const canUseAiEdits = Boolean(
    selectedLane && (selectedLane.variant === "ok" || selectedLane.variant === "alt")
  );
  const activeInspectorTab = inspectorTab === "ai" && !canUseAiEdits ? "clip" : inspectorTab;
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

  const addVolumeAutomationPoint = useCallback(() => {
    if (!selectedLane) return;
    const time = clamp(playhead - selectedLane.start, 0, selectedLane.duration);
    const point: AutomationPoint = {
      id: makeId(),
      time: Number(time.toFixed(2)),
      value: selectedLane.volume,
    };
    const points = (selectedLane.automation ?? []).filter(
      (existing) => Math.abs(existing.time - time) > 0.05
    );
    updateLane(selectedLane.id, {
      automation: [...points, point].sort((a, b) => a.time - b.time),
    });
  }, [playhead, selectedLane, updateLane]);

  const removeVolumeAutomationPoint = useCallback(
    (pointId: string) => {
      if (!selectedLane) return;
      updateLane(selectedLane.id, {
        automation: (selectedLane.automation ?? []).filter((point) => point.id !== pointId),
      });
    },
    [selectedLane, updateLane]
  );

  const addPanAutomationPoint = useCallback(() => {
    if (!selectedLane) return;
    const time = clamp(playhead - selectedLane.start, 0, selectedLane.duration);
    const point: AutomationPoint = {
      id: makeId(),
      time: Number(time.toFixed(2)),
      value: selectedLane.pan,
    };
    const points = (selectedLane.panAutomation ?? []).filter(
      (existing) => Math.abs(existing.time - time) > 0.05
    );
    updateLane(selectedLane.id, {
      panAutomation: [...points, point].sort((a, b) => a.time - b.time),
    });
  }, [playhead, selectedLane, updateLane]);

  const removePanAutomationPoint = useCallback(
    (pointId: string) => {
      if (!selectedLane) return;
      updateLane(selectedLane.id, {
        panAutomation: (selectedLane.panAutomation ?? []).filter(
          (point) => point.id !== pointId
        ),
      });
    },
    [selectedLane, updateLane]
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
      if (lane.midiNotes) {
        const midiKey = `${lane.generationId}:${lane.variant}`;
        const cachedMidi = buffersRef.current.get(midiKey);
        if (cachedMidi) return cachedMidi;
        const buffer = await renderMidiBuffer(
          lane.midiNotes,
          lane.duration,
          lane.instrument
        );
        buffersRef.current.set(midiKey, buffer);
        setAudioMeta((current) =>
          current[midiKey]
            ? current
            : {
                ...current,
                [midiKey]: { peaks: computePeaks(buffer), duration: buffer.duration },
              }
        );
        return buffer;
      }
      const key = lane.uploadId
        ? `upload:${lane.uploadId}`
        : lane.audioUrl
          ? `url:${lane.audioUrl}`
          : `${lane.generationId}:${lane.variant}`;
      const cached = buffersRef.current.get(key);
      if (cached) return cached;
      const context = ensureAudioContext();
      let sourceUrl = lane.audioUrl || null;
      if (lane.uploadId) {
        try {
          sourceUrl = await getStudioUploadUrl(lane.uploadId);
        } catch {
          sourceUrl = lane.audioUrl || null;
        }
      }
      let bytes: ArrayBuffer;
      if (sourceUrl) {
        const response = await fetch(sourceUrl, { credentials: "include" });
        if (!response.ok) throw new Error(`Could not load audio (${response.status}).`);
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

  const scheduleMetronome = useCallback(
    (context: AudioContext, startAt: number, from: number) => {
      const masterGain = masterGainRef.current;
      if (!metronomeRef.current || !masterGain) return;
      const [numerator, denominator] = timeSignature.split("/").map(Number);
      const beatsPerBar = Math.max(1, numerator || 4);
      const beat = (60 / Math.max(40, bpm)) * (4 / Math.max(1, denominator || 4));
      const end = loopRef.current ? loopEndRef.current : timelineDurationRef.current;
      let time = Math.ceil((from - 0.0001) / beat) * beat;
      if (time < from) time += beat;
      while (time < end) {
        const when = startAt + (time - from);
        if (when >= context.currentTime) {
          const beatIndex = Math.round(time / beat);
          const osc = context.createOscillator();
          const gain = context.createGain();
          osc.frequency.value = beatIndex % beatsPerBar === 0 ? 1600 : 1000;
          gain.gain.setValueAtTime(0.12, when);
          gain.gain.exponentialRampToValueAtTime(0.0001, when + 0.05);
          osc.connect(gain);
          gain.connect(masterGain);
          osc.start(when);
          osc.stop(when + 0.06);
          sourcesRef.current.push(osc);
        }
        time += beat;
      }
    },
    [bpm, timeSignature]
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
        scheduleMetronome(context, startedAt, from);
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
        scheduleMetronome(context, startAt, from);
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
          const startWhen = startAt + Math.max(0, lane.start - from);
          const chorusOut = context.createGain();
          connectTrackChorus(context, high, chorusOut, lane, startWhen, remaining);
          const driveOut = context.createGain();
          connectTrackDrive(context, chorusOut, driveOut, lane);
          connectTrackDynamics(context, driveOut, gain, lane);
          gain.connect(panner);
          const fx = connectTrackFx(context, panner, masterGain, lane);
          scheduleClipGain(gain, lane.volume / 100, lane, from, startWhen, remaining);
          schedulePanAutomation(panner, lane, from, startWhen, remaining);
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
    [ensureAudioContext, lanes, loadBuffer, scheduleMetronome, stopSources]
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
        return;
      }
      if (event.metaKey || event.ctrlKey || event.altKey) return;
      const key = event.key.toLowerCase();
      if (key === "s") {
        event.preventDefault();
        splitSelected();
      } else if (key === "d") {
        event.preventDefault();
        duplicateSelected();
      } else if (key === "m" && selectedLane) {
        event.preventDefault();
        updateLane(selectedLane.id, { muted: !selectedLane.muted });
      } else if (key === "l") {
        event.preventDefault();
        setLoop((value) => !value);
      } else if (key === "r") {
        event.preventDefault();
        if (recording) stopRecording();
        else void startRecording();
      } else if (event.key === "ArrowLeft" || event.key === "ArrowRight") {
        event.preventDefault();
        const step = event.shiftKey ? 5 : 1;
        seekTo(clamp(playhead + (event.key === "ArrowRight" ? step : -step), 0, timelineDuration));
      } else if (event.key === "Home") {
        event.preventDefault();
        seekTo(0);
      } else if (event.key === "End") {
        event.preventDefault();
        seekTo(timelineDuration);
      } else if (event.key === "Escape") {
        setSelected(null);
      }
    };
    window.addEventListener("keydown", handleKey);
    return () => window.removeEventListener("keydown", handleKey);
  }, [commitLanes, duplicateSelected, lanes, playhead, redo, recording, seekTo, selected, selectedLane, setLoop, splitSelected, startRecording, stopRecording, timelineDuration, togglePlay, undo, updateLane]);

  useEffect(() => {
    const handleLoopMove = (event: PointerEvent) => {
      const drag = loopDragRef.current;
      if (!drag || !drag.width) return;
      const delta = ((event.clientX - drag.startX) / drag.width) * timelineDurationRef.current;
      if (drag.which === "start") {
        setLoopStart(clamp(snapToGrid(drag.start + delta), 0, drag.end - 5));
      } else {
        setLoopEnd(clamp(snapToGrid(drag.end + delta), drag.start + 5, timelineDurationRef.current));
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
  }, [snapToGrid]);

  useEffect(() => {
    const handleMove = (event: PointerEvent) => {
      const drag = dragRef.current;
      if (!drag || !drag.trackWidth) return;
      const deltaSeconds = ((event.clientX - drag.startX) / drag.trackWidth) * timelineDurationRef.current;
      if (drag.mode === "move") {
        const nextStart = clamp(snapToGrid(drag.start + deltaSeconds), 0, timelineDurationRef.current - drag.duration);
        setLanes((current) =>
          current.map((lane) => (lane.id === drag.id ? { ...lane, start: nextStart } : lane))
        );
        return;
      }
      if (drag.mode === "left") {
        const minStart = Math.max(0, drag.start - drag.offset);
        const nextStart = clamp(
          snapToGrid(drag.start + deltaSeconds),
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
        snapToGrid(drag.duration + deltaSeconds),
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
  }, [snapToGrid]);

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

  function addMarker() {
    const label = window.prompt("Section name", `Section ${markers.length + 1}`);
    if (label === null) return;
    const title = label.trim().slice(0, 80);
    if (!title) return;
    const marker: TimelineMarker = {
      id: makeId(),
      time: Number(clamp(playhead, 0, timelineDuration).toFixed(2)),
      label: title,
      color: COLORS[markers.length % COLORS.length],
    };
    setMarkers((current) =>
      [...current, marker].sort((a, b) => a.time - b.time)
    );
  }

  function renameMarker(marker: TimelineMarker) {
    const label = window.prompt("Section name", marker.label);
    if (label === null) return;
    const title = label.trim().slice(0, 80);
    if (!title) return;
    setMarkers((current) =>
      current.map((item) => (item.id === marker.id ? { ...item, label: title } : item))
    );
  }

  function removeMarker(marker: TimelineMarker) {
    if (!window.confirm(`Remove section "${marker.label}"?`)) return;
    setMarkers((current) => current.filter((item) => item.id !== marker.id));
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

  async function startRecording() {
    if (recording || importing) return;
    if (!navigator.mediaDevices?.getUserMedia || typeof MediaRecorder === "undefined") {
      setRecordError("Microphone recording is not supported in this browser.");
      return;
    }
    setRecordError("");
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const mimeType = MediaRecorder.isTypeSupported("audio/webm;codecs=opus")
        ? "audio/webm;codecs=opus"
        : "audio/webm";
      const recorder = new MediaRecorder(stream, { mimeType });
      recordStreamRef.current = stream;
      recorderRef.current = recorder;
      recordChunksRef.current = [];
      recorder.ondataavailable = (event) => {
        if (event.data.size > 0) recordChunksRef.current.push(event.data);
      };
      recorder.onerror = () => {
        setRecordError("Recording failed. Check the microphone permission.");
        setRecording(false);
      };
      recorder.onstop = () => {
        if (recordTimerRef.current !== null) {
          window.clearInterval(recordTimerRef.current);
          recordTimerRef.current = null;
        }
        stream.getTracks().forEach((track) => track.stop());
        recordStreamRef.current = null;
        setRecording(false);
        const blob = new Blob(recordChunksRef.current, {
          type: recorder.mimeType || "audio/webm",
        });
        recordChunksRef.current = [];
        if (blob.size > 0) {
          const stamp = new Date().toISOString().replace(/[:.]/g, "-").slice(0, 19);
          const file = new File([blob], `Recording ${stamp}.webm`, {
            type: blob.type || "audio/webm",
          });
          void importAudioFile(file);
        }
      };
      recorder.start(250);
      setRecording(true);
      setRecordSeconds(0);
      recordTimerRef.current = window.setInterval(
        () => setRecordSeconds((value) => value + 1),
        1000
      );
    } catch (cause) {
      recordStreamRef.current?.getTracks().forEach((track) => track.stop());
      recordStreamRef.current = null;
      setRecordError(
        cause instanceof Error ? cause.message : "Could not access the microphone."
      );
    }
  }

  function stopRecording() {
    if (recordTimerRef.current !== null) {
      window.clearInterval(recordTimerRef.current);
      recordTimerRef.current = null;
    }
    if (recorderRef.current && recorderRef.current.state !== "inactive") {
      recorderRef.current.stop();
    }
  }

  async function importAudioFile(file: File) {
    if (importing) return;
    if (file.size > 50 * 1024 * 1024) {
      setImportError("Audio imports are limited to 50 MB.");
      return;
    }
    setImporting(true);
    setImportError("");
    try {
      const bytes = await file.arrayBuffer();
      const context = ensureAudioContext();
      const buffer = await context.decodeAudioData(bytes.slice(0));
      const typedFile =
        file.type && file.type.startsWith("audio/")
          ? file
          : new File([file], file.name, { type: "audio/mpeg" });
      const upload = await uploadStudioAudio(typedFile, buffer.duration);
      const duration = Math.max(1, buffer.duration);
      const title = file.name.replace(/\.[^.]+$/, "") || "Imported audio";
      const lane: Clip = {
        id: makeId(),
        generationId: `upload:${upload.id}`,
        variant: "upload",
        title,
        style: "Imported audio",
        color: COLORS[lanes.length % COLORS.length],
        image: null,
        start: clamp(playhead, 0, Math.max(0, timelineDuration - duration)),
        duration,
        offset: 0,
        fadeIn: 0,
        fadeOut: 0,
        automation: [],
        panAutomation: [],
        audioUrl: upload.url,
        uploadId: upload.id,
        low: 0,
        mid: 0,
        high: 0,
        delay: 0,
        reverb: 0,
        chorus: 0,
        compressor: 0,
        drive: 0,
        volume: 80,
        pan: 0,
        muted: false,
        solo: false,
      };
      commitLanes([...lanes, lane]);
      setSelected(lane.id);
    } catch (cause) {
      setImportError(cause instanceof Error ? cause.message : "Could not import audio.");
    } finally {
      setImporting(false);
    }
  }

  function addMidiTrack() {
    const id = makeId();
    const lane: Clip = {
      id,
      generationId: `midi:${id}`,
      variant: "midi",
      title: "MIDI Instrument",
      style: "MIDI synth",
      color: COLORS[lanes.length % COLORS.length],
      image: null,
      start: clamp(playhead, 0, Math.max(0, timelineDuration - 8)),
      duration: 8,
      offset: 0,
      fadeIn: 0,
      fadeOut: 0,
      automation: [],
      panAutomation: [],
      audioUrl: null,
      midiNotes: [],
      instrument: "triangle",
      low: 0,
      mid: 0,
      high: 0,
      delay: 0,
      reverb: 0,
      chorus: 0,
      compressor: 0,
      drive: 0,
      volume: 80,
      pan: 0,
      muted: false,
      solo: false,
    };
    commitLanes([...lanes, lane]);
    setSelected(lane.id);
  }

  function midiCacheKey(lane: Clip): string {
    return `${lane.generationId}:${lane.variant}`;
  }

  function invalidateMidi(lane: Clip) {
    const key = midiCacheKey(lane);
    buffersRef.current.delete(key);
    setAudioMeta((current) => {
      if (!current[key]) return current;
      const next = { ...current };
      delete next[key];
      return next;
    });
  }

  function toggleMidiNote(time: number, pitch: number) {
    if (!selectedLane?.midiNotes) return;
    const notes = selectedLane.midiNotes;
    const existing = notes.find(
      (note) => Math.abs(note.time - time) < 0.01 && note.pitch === pitch
    );
    const next = existing
      ? notes.filter((note) => note.id !== existing.id)
      : [
          ...notes,
          {
            id: makeId(),
            time,
            pitch,
            duration: 0.45,
            velocity: 0.8,
          } satisfies MidiNote,
        ];
    invalidateMidi(selectedLane);
    updateLane(selectedLane.id, { midiNotes: next });
  }

  function duplicateLane(lane: Clip) {
    const copy: Clip = {
      ...lane,
      id: makeId(),
      start: clamp(lane.start + 2, 0, timelineDuration - lane.duration),
      color: COLORS[lanes.length % COLORS.length],
    };
    commitLanes([...lanes, copy]);
    setSelected(copy.id);
  }

  function splitLane(lane: Clip, at: number) {
    const local = at - lane.start;
    if (local <= MIN_CLIP || local >= lane.duration - MIN_CLIP) return;
    const automation = lane.automation ?? [];
    const panAutomation = lane.panAutomation ?? [];
    const left: Clip = {
      ...lane,
      duration: local,
      fadeOut: 0,
      automation: automation.filter((point) => point.time <= local),
      panAutomation: panAutomation.filter((point) => point.time <= local),
    };
    const right: Clip = {
      ...lane,
      id: makeId(),
      start: at,
      duration: lane.duration - local,
      offset: lane.offset + local,
      fadeIn: 0,
      automation: automation
        .filter((point) => point.time >= local)
        .map((point) => ({ ...point, time: point.time - local })),
      panAutomation: panAutomation
        .filter((point) => point.time >= local)
        .map((point) => ({ ...point, time: point.time - local })),
    };
    commitLanes(lanes.flatMap((item) => (item.id === lane.id ? [left, right] : [item])));
    setSelected(right.id);
  }

  function duplicateSelected() {
    if (selectedLane) duplicateLane(selectedLane);
  }

  function splitSelected() {
    if (selectedLane) splitLane(selectedLane, playhead);
  }

  function renameLane(lane: Clip) {
    const next = window.prompt("Track name", lane.title);
    if (next === null) return;
    const title = next.trim().slice(0, 80);
    if (title) updateLane(lane.id, { title });
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
      const when = clipStart - start;
      const chorusOut = offline.createGain();
      connectTrackChorus(offline, high, chorusOut, lane, when, length);
      const driveOut = offline.createGain();
      connectTrackDrive(offline, chorusOut, driveOut, lane);
      connectTrackDynamics(offline, driveOut, gain, lane);
      gain.connect(panner);
      connectTrackFx(offline, panner, masterGain, lane);
      scheduleClipGain(gain, lane.volume / 100, lane, clipStart, when, length);
      schedulePanAutomation(panner, lane, clipStart, when, length);
      source.start(when, offset, length);
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
        automation: [],
        panAutomation: [],
        audioUrl,
        low: 0,
        mid: 0,
        high: 0,
        delay: 0,
        reverb: 0,
        chorus: 0,
        compressor: 0,
        drive: 0,
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

  function runAiCommand() {
    const command = aiPrompt.trim();
    if (!command) return;
    if (!selectedLane) {
      setAiStatus("Select a clip first, then ask Studio to edit it.");
      return;
    }
    const lower = command.toLowerCase();
    if (lower.includes("stem")) {
      setAiStatus("Separating stems…");
      void separateStems("stems");
      return;
    }
    if (lower.includes("extend")) {
      setAiStatus("Extending the selected clip…");
      void runStudioEdit("Extend", () =>
        requestStudioExtend({
          taskId: selectedLane.generationId,
          variant: selectedLane.variant,
          continueAt: Math.round(selectedLane.start + selectedLane.duration),
          projectId,
        })
      );
      return;
    }
    if (lower.includes("cover")) {
      setAiStatus("Creating a cover…");
      void runStudioEdit("Cover", () =>
        requestStudioCover({
          taskId: selectedLane.generationId,
          variant: selectedLane.variant,
          prompt: command,
          projectId,
        })
      );
      return;
    }
    if (lower.includes("vocal")) {
      setAiStatus("Adding vocals…");
      void runStudioEdit("Add vocals", () =>
        requestStudioAddVocals({
          taskId: selectedLane.generationId,
          variant: selectedLane.variant,
          prompt: command,
          projectId,
        })
      );
      return;
    }
    if (lower.includes("instrumental")) {
      setAiStatus("Adding instrumental…");
      void runStudioEdit("Add instrumental", () =>
        requestStudioAddInstrumental({
          taskId: selectedLane.generationId,
          variant: selectedLane.variant,
          prompt: command,
          projectId,
        })
      );
      return;
    }
    setAiStatus("Try: stems, extend, cover, add vocals, or add instrumental.");
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
          automation: [],
          panAutomation: [],
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
          chorus: 0,
          compressor: 0,
          drive: 0,
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
        <div className="studio-top-stats">
          <span>{formatTime(playhead)}</span>
          <span>{barBeat}</span>
          <span>{bpm} BPM</span>
          <select
            className="studio-timesig"
            value={timeSignature}
            onChange={(event) => setTimeSignature(event.target.value)}
            aria-label="Time signature"
          >
            <option value="4/4">4/4</option>
            <option value="3/4">3/4</option>
            <option value="6/8">6/8</option>
          </select>
        </div>
        <div className="studio-top-actions">
          {sharedToken && collaborators.length ? (
            <div
              className="studio-presence"
              title={collaborators.map((person) => person.display_name).join(", ")}
            >
              {collaborators.slice(0, 3).map((person) => (
                <span key={person.user_id}>
                  {person.display_name.slice(0, 1).toUpperCase()}
                </span>
              ))}
              {collaborators.length > 1 ? <em>{collaborators.length}</em> : null}
            </div>
          ) : null}
          <button
            className={`studio-icon-btn${libraryOpen ? " on" : ""}`}
            type="button"
            aria-label="Toggle Library"
            aria-pressed={libraryOpen}
            title="Library"
            onClick={() => {
              setActionsOpen(false);
              setLibraryOpen((value) => !value);
            }}
          >
            <Icon name="fa-table-columns" />
          </button>
          <button
            className={`studio-icon-btn${inspectorOpen ? " on" : ""}`}
            type="button"
            aria-label="Toggle Inspector"
            aria-pressed={inspectorOpen}
            title="Inspector"
            onClick={() => {
              setActionsOpen(false);
              setInspectorOpen((value) => !value);
            }}
          >
            <Icon name="fa-sliders" />
          </button>
          {recording ? (
            <button className="btn btn-ghost studio-record-btn recording" type="button" onClick={stopRecording}>
              <Icon name="fa-stop" /> {String(Math.floor(recordSeconds / 60)).padStart(2, "0")}:{String(recordSeconds % 60).padStart(2, "0")}
            </button>
          ) : null}
          <div className="studio-actions-menu-wrap">
            <button
              className="studio-icon-btn"
              type="button"
              aria-label="More project actions"
              aria-expanded={actionsOpen}
              title="Project actions"
              onClick={() => setActionsOpen((value) => !value)}
            >
              <Icon name="fa-ellipsis" />
            </button>
            {actionsOpen ? (
              <>
                <div className="studio-actions-menu">
                  <button type="button" onClick={() => { setActionsOpen(false); void openProjects(); }}>
                    <Icon name="fa-folder-open" /> Open project
                  </button>
                  <button
                    type="button"
                    onClick={() => {
                      setActionsOpen(false);
                      if (!window.confirm("Clear this session? This does not delete your songs.")) return;
                      commitLanes([]);
                      setSelected(null);
                      setPlayhead(0);
                      setProjectId(null);
                      setCloudState("local");
                      setSessionName("Untitled session");
                    }}
                  >
                    <Icon name="fa-file-circle-plus" /> New session
                  </button>
                  <button type="button" onClick={() => { setActionsOpen(false); void openVersions(); }}>
                    <Icon name="fa-clock-rotate-left" /> Versions
                  </button>
                  <button type="button" onClick={() => { setActionsOpen(false); openShare(); }}>
                    <Icon name="fa-share-nodes" /> Share
                  </button>
                  <Link href="/create" onClick={() => setActionsOpen(false)}>
                    <Icon name="fa-plus" /> Create a track
                  </Link>
                  <label>
                    <Icon name={importing ? "fa-spinner" : "fa-upload"} /> Import audio
                    <input
                      type="file"
                      accept="audio/*"
                      disabled={importing}
                      onChange={(event) => {
                        const file = event.currentTarget.files?.[0];
                        if (file) void importAudioFile(file);
                        event.currentTarget.value = "";
                        setActionsOpen(false);
                      }}
                      hidden
                    />
                  </label>
                  <button type="button" onClick={() => { setActionsOpen(false); void startRecording(); }}>
                    <Icon name="fa-microphone" /> Record
                  </button>
                  <button type="button" onClick={() => { setActionsOpen(false); addMidiTrack(); }}>
                    <Icon name="fa-music" /> MIDI track
                  </button>
                </div>
              </>
            ) : null}
          </div>
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
              className="btn btn-ghost studio-export-stems"
              type="button"
              disabled={!lanes.length || exporting}
              onClick={() => void exportStems()}
              title="Export each unmuted track into one ZIP archive"
            >
              <Icon name="fa-layer-group" /> <span>{exporting ? "Rendering?" : "Stems"}</span>
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
      {importError || recordError ? (
        <div className="studio-head-errors">
          {importError ? <small>{importError}</small> : null}
          {recordError ? <small>{recordError}</small> : null}
        </div>
      ) : null}
      {remoteChanges ? (
        <div className="studio-remote-banner" role="status">
          <Icon name="fa-arrows-rotate" /> Collaborator changes are available.
          <button type="button" onClick={() => void reloadSharedProject()}>
            Reload
          </button>
        </div>
      ) : null}

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
        <button className="studio-icon-btn" type="button" aria-label="Add section marker" onClick={addMarker} title="Add section marker at playhead">
          <Icon name="fa-flag" />
        </button>
        <span className="studio-toolbar-divider" />
        <label className="studio-bpm">BPM <input type="number" min={40} max={220} value={bpm} onChange={(event) => setBpm(clamp(Number(event.target.value), 40, 220))} /></label>
        <label className="studio-snap-grid">Grid
          <select value={gridDivision} onChange={(event) => setGridDivision(event.target.value as typeof gridDivision)} aria-label="Snap grid">
            <option value="off">Off</option>
            <option value="bar">Bar</option>
            <option value="beat">Beat</option>
            <option value="1/8">1/8</option>
            <option value="1/16">1/16</option>
          </select>
        </label>
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

      <div className={`studio-work${libraryOpen ? "" : " library-closed"}${inspectorOpen ? "" : " inspector-closed"}`}>
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
          <div className="studio-library-filters" role="group" aria-label="Library filters">
            {([
              ["all", "All"],
              ["instrumental", "Instrumental"],
              ["vocal", "Vocals"],
              ["ready", "Ready"],
            ] as const).map(([value, label]) => (
              <button
                key={value}
                className={libraryFilter === value ? "active" : ""}
                type="button"
                aria-pressed={libraryFilter === value}
                onClick={() => setLibraryFilter(value)}
              >
                {label}
              </button>
            ))}
          </div>
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
              {markers.map((marker) => (
                <button
                  className="studio-marker"
                  key={marker.id}
                  type="button"
                  style={{
                    left: `${(clamp(marker.time, 0, timelineDuration) / timelineDuration) * 100}%`,
                    color: marker.color,
                    borderColor: `${marker.color}66`,
                  }}
                  title={`${marker.label} — click to seek, double-click to rename, right-click to remove`}
                  onClick={(event) => {
                    event.stopPropagation();
                    seekTo(marker.time);
                  }}
                  onDoubleClick={(event) => {
                    event.stopPropagation();
                    renameMarker(marker);
                  }}
                  onContextMenu={(event) => {
                    event.preventDefault();
                    event.stopPropagation();
                    removeMarker(marker);
                  }}
                >
                  <span>{marker.label}</span>
                </button>
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
                <button className="studio-lane-head" type="button" onClick={() => setSelected(lane.id)} onDoubleClick={() => renameLane(lane)} title="Double-click to rename">
                  <span className="studio-lane-index" style={{ color: lane.color, borderColor: `${lane.color}66` }}>
                    {String(index + 1).padStart(2, "0")}
                  </span>
                  <span className="studio-lane-copy">
                    <b>{lane.title}</b>
                    <small>
                      {lane.midiNotes
                        ? "MIDI instrument"
                        : lane.uploadId
                          ? "Audio recording"
                          : "Audio track"}{" "}
                      ? {formatTime(lane.start)}
                    </small>
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
                    onContextMenu={(event) => {
                      event.preventDefault();
                      setSelected(lane.id);
                      setClipMenu({ x: event.clientX, y: event.clientY, laneId: lane.id });
                    }}
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
            <div className="studio-add-lane">
              <button type="button" onClick={() => setActionsOpen(true)}>
                <Icon name="fa-plus" /> Add track
              </button>
            </div>
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
              <div className="studio-inspector-tabs" role="tablist">
                {(["clip", "mix"] as const).map((tab) => (
                  <button
                    key={tab}
                    className={activeInspectorTab === tab ? "active" : ""}
                    type="button"
                    role="tab"
                    aria-selected={activeInspectorTab === tab}
                    onClick={() => setInspectorTab(tab)}
                  >
                    {tab === "clip" ? "Clip" : "Mix"}
                  </button>
                ))}
                {canUseAiEdits ? (
                  <button
                    className={activeInspectorTab === "ai" ? "active" : ""}
                    type="button"
                    role="tab"
                    aria-selected={activeInspectorTab === "ai"}
                    onClick={() => setInspectorTab("ai")}
                  >
                    AI
                  </button>
                ) : null}
              </div>
              {activeInspectorTab === "clip" ? (
                <>
              {selectedLane.midiNotes ? (
                <div className="studio-midi">
                  <div className="studio-eq-head">
                    <span>Piano roll</span>
                    <div className="studio-midi-head-actions">
                      <select
                        value={selectedLane.instrument ?? "triangle"}
                        onChange={(event) => {
                          invalidateMidi(selectedLane);
                          updateLane(selectedLane.id, {
                            instrument: event.target.value as Clip["instrument"],
                          });
                        }}
                        aria-label="MIDI instrument"
                      >
                        <option value="triangle">Triangle</option>
                        <option value="sine">Sine</option>
                        <option value="sawtooth">Saw</option>
                      </select>
                      <button
                        type="button"
                        onClick={() => {
                          invalidateMidi(selectedLane);
                          updateLane(selectedLane.id, { midiNotes: [] });
                        }}
                      >
                        Clear
                      </button>
                    </div>
                  </div>
                  <div className="studio-midi-grid">
                    {[71, 70, 69, 68, 67, 66, 65, 64, 63, 62, 61, 60].map((pitch) => (
                      <div className="studio-midi-row" key={pitch}>
                        <span>{midiNoteName(pitch)}</span>
                        {Array.from({ length: 16 }, (_, step) => {
                          const time = step * 0.5;
                          const active = (selectedLane.midiNotes ?? []).some(
                            (note) =>
                              note.pitch === pitch &&
                              Math.abs(note.time - time) < 0.01
                          );
                          return (
                            <button
                              className={active ? "on" : ""}
                              key={step}
                              type="button"
                              aria-label={`${midiNoteName(pitch)} at ${time}s`}
                              onClick={() => toggleMidiNote(time, pitch)}
                            />
                          );
                        })}
                      </div>
                    ))}
                  </div>
                </div>
              ) : null}
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
                </>
              ) : null}
              {activeInspectorTab === "mix" ? (
                <>
              <div className="studio-eq studio-automation">
                <div className="studio-eq-head">
                  <span>Volume automation</span>
                  <button type="button" onClick={addVolumeAutomationPoint}>Add at playhead</button>
                </div>
                {(selectedLane.automation ?? []).length ? (
                  <div className="studio-automation-points">
                    {(selectedLane.automation ?? []).map((point) => (
                      <div className="studio-automation-point" key={point.id}>
                        <span>{point.time.toFixed(1)}s</span>
                        <b>{Math.round(point.value)}%</b>
                        <button type="button" aria-label="Remove automation point" onClick={() => removeVolumeAutomationPoint(point.id)}>
                          <Icon name="fa-xmark" />
                        </button>
                      </div>
                    ))}
                  </div>
                ) : (
                  <small>Add a point at the playhead. Automation overrides fades.</small>
                )}
              </div>
              <div className="studio-eq studio-automation">
                <div className="studio-eq-head">
                  <span>Pan automation</span>
                  <button type="button" onClick={addPanAutomationPoint}>Add at playhead</button>
                </div>
                {(selectedLane.panAutomation ?? []).length ? (
                  <div className="studio-automation-points">
                    {(selectedLane.panAutomation ?? []).map((point) => (
                      <div className="studio-automation-point" key={point.id}>
                        <span>{point.time.toFixed(1)}s</span>
                        <b>{point.value === 0 ? "C" : point.value > 0 ? `R${Math.round(point.value)}` : `L${Math.round(Math.abs(point.value))}`}</b>
                        <button type="button" aria-label="Remove pan automation point" onClick={() => removePanAutomationPoint(point.id)}>
                          <Icon name="fa-xmark" />
                        </button>
                      </div>
                    ))}
                  </div>
                ) : (
                  <small>Add a point at the playhead to automate stereo position.</small>
                )}
              </div>
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
                  <button type="button" onClick={() => updateLane(selectedLane.id, { delay: 0, reverb: 0, chorus: 0 })}>Reset</button>
                </div>
                <label>Delay <b>{selectedLane.delay}%</b>
                  <input type="range" min="0" max="100" step="1" value={selectedLane.delay} onChange={(event) => updateLane(selectedLane.id, { delay: Number(event.target.value) })} />
                </label>
                <label>Reverb <b>{selectedLane.reverb}%</b>
                  <input type="range" min="0" max="100" step="1" value={selectedLane.reverb} onChange={(event) => updateLane(selectedLane.id, { reverb: Number(event.target.value) })} />
                </label>
                <label>Chorus <b>{selectedLane.chorus}%</b>
                  <input type="range" min="0" max="100" step="1" value={selectedLane.chorus} onChange={(event) => updateLane(selectedLane.id, { chorus: Number(event.target.value) })} />
                </label>
              </div>
              <div className="studio-eq">
                <div className="studio-eq-head">
                  <span>Dynamics</span>
                  <button type="button" onClick={() => updateLane(selectedLane.id, { compressor: 0, drive: 0 })}>Reset</button>
                </div>
                <label>Compression <b>{selectedLane.compressor}%</b>
                  <input type="range" min="0" max="100" step="1" value={selectedLane.compressor} onChange={(event) => updateLane(selectedLane.id, { compressor: Number(event.target.value) })} />
                </label>
                <label>Drive <b>{selectedLane.drive}%</b>
                  <input type="range" min="0" max="100" step="1" value={selectedLane.drive} onChange={(event) => updateLane(selectedLane.id, { drive: Number(event.target.value) })} />
                </label>
              </div>
                </>
              ) : null}
              <div className="studio-inspector-actions">
                <button className={selectedLane.muted ? "on" : ""} type="button" onClick={() => updateLane(selectedLane.id, { muted: !selectedLane.muted })}>Mute</button>
                <button className={selectedLane.solo ? "on" : ""} type="button" onClick={() => updateLane(selectedLane.id, { solo: !selectedLane.solo })}>Solo</button>
              </div>
              <div className="studio-inspector-actions">
                <button type="button" onClick={splitSelected} disabled={!canSplit}>Split</button>
                <button type="button" onClick={duplicateSelected}>Duplicate</button>
              </div>
              {activeInspectorTab === "ai" ? (
                canUseAiEdits ? (
                <>
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
                </>
                ) : (
                  <div className="studio-ai-unavailable">
                    <Icon name="fa-circle-info" /> Stem separation and AI edits are available on original generated clips.
                  </div>
                )
              ) : null}
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

      <form
        className="studio-ai-bar"
        onSubmit={(event) => {
          event.preventDefault();
          runAiCommand();
        }}
      >
        <span className="studio-ai-label">
          <Icon name="fa-wand-magic-sparkles" /> Studio AI <em>BETA</em>
        </span>
        <input
          value={aiPrompt}
          onChange={(event) => setAiPrompt(event.target.value)}
          placeholder="Select a clip and ask me to add or change a part…"
          aria-label="Studio AI prompt"
        />
        <button type="submit" disabled={!aiPrompt.trim()} aria-label="Run Studio AI command">
          <Icon name="fa-arrow-up" />
        </button>
        {aiStatus ? <small>{aiStatus}</small> : null}
      </form>

      <div className="studio-transport">
        <span className="studio-transport-left"><Icon name="fa-wave-square" /> {bpm} BPM ? {timeSignature}</span>
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
          <button
            className={`studio-loop-btn${metronome ? " on" : ""}`}
            type="button"
            aria-label="Metronome"
            aria-pressed={metronome}
            title="Metronome"
            onClick={() => setMetronome((value) => !value)}
          >
            <Icon name="fa-bell" />
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
      {versionsOpen ? (
        <div className="studio-modal-backdrop" role="dialog" aria-modal="true" aria-label="Project versions">
          <div className="studio-versions-modal">
            <div className="studio-versions-head">
              <div>
                <h2>Project versions</h2>
                <p>Snapshots are stored with the cloud project.</p>
              </div>
              <button type="button" aria-label="Close versions" onClick={() => setVersionsOpen(false)}>
                <Icon name="fa-xmark" />
              </button>
            </div>
            <div className="studio-versions-save">
              <input
                value={versionLabel}
                onChange={(event) => setVersionLabel(event.target.value)}
                placeholder="Version label (optional)"
                maxLength={120}
                disabled={!projectId || versionsBusy}
              />
              <button
                className="btn btn-primary"
                type="button"
                onClick={() => void saveVersion()}
                disabled={!projectId || versionsBusy}
              >
                <Icon name="fa-camera" /> Save current
              </button>
            </div>
            {versionsError ? <small className="studio-stem-error">{versionsError}</small> : null}
            <div className="studio-versions-list">
              {versionsBusy && !versions.length ? <p>Loading versions…</p> : null}
              {!versionsBusy && !versions.length ? <p>No versions saved yet.</p> : null}
              {versions.map((version) => (
                <div className="studio-version-row" key={version.id}>
                  <div>
                    <b>{version.label || version.title}</b>
                    <small>
                      {version.created_at
                        ? new Date(version.created_at).toLocaleString()
                        : version.title}
                    </small>
                  </div>
                  <button
                    type="button"
                    onClick={() => void restoreVersion(version)}
                    disabled={versionsBusy}
                  >
                    Restore
                  </button>
                </div>
              ))}
            </div>
          </div>
        </div>
      ) : null}
      {projectsOpen ? (
        <div className="studio-modal-backdrop" role="dialog" aria-modal="true" aria-label="Open project">
          <div className="studio-versions-modal">
            <div className="studio-versions-head">
              <div>
                <h2>Open project</h2>
                <p>Choose a saved Studio project.</p>
              </div>
              <button type="button" aria-label="Close projects" onClick={() => setProjectsOpen(false)}>
                <Icon name="fa-xmark" />
              </button>
            </div>
            {projectsError ? <small className="studio-stem-error">{projectsError}</small> : null}
            <div className="studio-versions-list">
              {projectsBusy && !projectList.length ? <p>Loading projects…</p> : null}
              {!projectsBusy && !projectList.length ? <p>No saved projects yet.</p> : null}
              {projectList.map((project) => (
                <div className="studio-version-row" key={project.id}>
                  <div>
                    <b>{project.title}</b>
                    <small>
                      {project.updated_at
                        ? new Date(project.updated_at).toLocaleString()
                        : "Saved project"}
                    </small>
                  </div>
                  <div className="studio-project-actions">
                    <button
                      type="button"
                      onClick={() => void renameProject(project)}
                      disabled={projectsBusy}
                    >
                      Rename
                    </button>
                    <button
                      className="danger"
                      type="button"
                      onClick={() => void deleteProject(project)}
                      disabled={projectsBusy}
                    >
                      Delete
                    </button>
                    <button
                      type="button"
                      onClick={() => void openProject(project.id)}
                      disabled={projectsBusy}
                    >
                      Open
                    </button>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      ) : null}
      {shareOpen ? (
        <div className="studio-modal-backdrop" role="dialog" aria-modal="true" aria-label="Share project">
          <div className="studio-versions-modal studio-share-modal">
            <div className="studio-versions-head">
              <div>
                <h2>Share project</h2>
                <p>Create a read-only link that expires in 7 days.</p>
              </div>
              <button type="button" aria-label="Close share" onClick={() => setShareOpen(false)}>
                <Icon name="fa-xmark" />
              </button>
            </div>
            {shareUrl ? (
              <>
                <div className="studio-share-link">
                  <input readOnly value={shareUrl} onFocus={(event) => event.currentTarget.select()} />
                  <button className="btn btn-primary" type="button" onClick={() => void copyShare()}>
                    <Icon name="fa-copy" /> Copy
                  </button>
                </div>
                <a className="studio-share-open" href={shareUrl} target="_blank" rel="noreferrer">
                  Open read-only preview <Icon name="fa-arrow-up-right-from-square" />
                </a>
              </>
             ) : (
              <>
                <label className="studio-share-permission">
                  Link access
                  <select
                    value={sharePermission}
                    onChange={(event) => setSharePermission(event.target.value as "view" | "edit")}
                    disabled={shareBusy}
                  >
                    <option value="view">View only</option>
                    <option value="edit">Can edit</option>
                  </select>
                </label>
                <button className="btn btn-primary" type="button" onClick={() => void createShare()} disabled={shareBusy || !projectId}>
                  <Icon name={shareBusy ? "fa-spinner" : "fa-link"} />
                  {shareBusy ? "Creating?" : "Create share link"}
                </button>
              </>
            )}
            {shareError ? <small className="studio-stem-error">{shareError}</small> : null}
            <div className="studio-project-comments">
              <div className="studio-project-comments-head">
                <span>Comments</span>
                <em>{projectComments.length}</em>
              </div>
              {commentsBusy ? <small>Loading comments…</small> : null}
              {commentsError ? <small className="studio-stem-error">{commentsError}</small> : null}
              {!commentsBusy && !projectComments.length ? (
                <small>No comments yet. Share the link to collect feedback.</small>
              ) : null}
              {projectComments.map((comment) => (
                <div className="studio-project-comment" key={comment.id}>
                  <header>
                    <b>{comment.author_name}</b>
                    <span>
                      {comment.created_at
                        ? new Date(comment.created_at).toLocaleString()
                        : ""}
                    </span>
                  </header>
                  <p>{comment.body}</p>
                </div>
              ))}
            </div>
          </div>
        </div>
      ) : null}
      {clipMenu ? (() => {
        const lane = lanes.find((item) => item.id === clipMenu.laneId);
        if (!lane) return null;
        return (
          <div
            className="studio-clip-menu"
            role="menu"
            style={{
              left: Math.min(clipMenu.x, window.innerWidth - 190),
              top: Math.min(clipMenu.y, window.innerHeight - 230),
            }}
          >
            <div className="studio-clip-menu-head">{lane.title}</div>
            <button type="button" onClick={() => { setClipMenu(null); splitLane(lane, playhead); }}>
              <Icon name="fa-scissors" /> Split at playhead
            </button>
            <button type="button" onClick={() => { setClipMenu(null); duplicateLane(lane); }}>
              <Icon name="fa-copy" /> Duplicate
            </button>
            <button type="button" onClick={() => { setClipMenu(null); updateLane(lane.id, { muted: !lane.muted }); }}>
              <Icon name={lane.muted ? "fa-volume-high" : "fa-volume-xmark"} /> {lane.muted ? "Unmute" : "Mute"}
            </button>
            <button type="button" onClick={() => { setClipMenu(null); renameLane(lane); }}>
              <Icon name="fa-pen" /> Rename track
            </button>
            <button className="danger" type="button" onClick={() => { setClipMenu(null); commitLanes(lanes.filter((item) => item.id !== lane.id)); }}>
              <Icon name="fa-trash" /> Remove from session
            </button>
          </div>
        );
      })() : null}
    </div>
  );
}
