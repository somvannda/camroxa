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
  requestStudioRemaster,
  requestStudioMashup,
  requestStudioCoverImage,
  requestStudioUploadExtend,
  requestStudioUploadCover,
  getStudioOperation,
  getStudioLyrics,
  type StudioLyrics,
  createStudioPersona,
  listStudioPersonas,
  type StudioPersona,
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
  revokeStudioProjectShare,
  listStudioProjectComments,
  getStudioSharedProject,
  updateStudioSharedProject,
  deleteStudioProject,
  forkStudioProject,
  touchStudioPresence,
  type StudioPresence,
} from "@/lib/studio-api";

type AutomationPoint = {
  id: string;
  time: number;
  value: number;
  curve?: "linear" | "exponential";
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
  fadeInCurve?: "linear" | "exponential";
  fadeOutCurve?: "linear" | "exponential";
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
  filterCutoff?: number;
  filterResonance?: number;
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
  masterCompressor?: number;
  masterDrive?: number;
  masterLow?: number;
  masterMid?: number;
  masterHigh?: number;
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

type MasterPresetPatch = {
  master: number;
  masterCompressor: number;
  masterDrive: number;
  masterLow: number;
  masterMid: number;
  masterHigh: number;
};

const MASTER_PRESETS: Array<{
  id: string;
  name: string;
  patch: MasterPresetPatch;
}> = [
  {
    id: "clean",
    name: "Clean",
    patch: {
      master: 100,
      masterCompressor: 0,
      masterDrive: 0,
      masterLow: 0,
      masterMid: 0,
      masterHigh: 0,
    },
  },
  {
    id: "warm",
    name: "Warm",
    patch: {
      master: 96,
      masterCompressor: 15,
      masterDrive: 12,
      masterLow: 1.5,
      masterMid: -1,
      masterHigh: -1,
    },
  },
  {
    id: "loud",
    name: "Loud",
    patch: {
      master: 92,
      masterCompressor: 45,
      masterDrive: 20,
      masterLow: 1,
      masterMid: 0,
      masterHigh: 1,
    },
  },
  {
    id: "transparent",
    name: "Transparent",
    patch: {
      master: 100,
      masterCompressor: 8,
      masterDrive: 0,
      masterLow: 0,
      masterMid: 0,
      masterHigh: 0,
    },
  },
];

const MIX_PRESETS: Array<{ id: string; name: string; patch: Partial<Clip> }> = [
  {
    id: "clean",
    name: "Clean",
    patch: {
      low: 0,
      mid: 0,
      high: 0,
      delay: 0,
      reverb: 0,
      chorus: 0,
      compressor: 0,
      drive: 0,
      filterCutoff: 20000,
      filterResonance: 0.7,
    },
  },
  {
    id: "vocal",
    name: "Vocal focus",
    patch: {
      low: -2,
      mid: 2,
      high: 1.5,
      delay: 6,
      reverb: 12,
      chorus: 8,
      compressor: 35,
      drive: 0,
      filterCutoff: 16000,
      filterResonance: 1,
    },
  },
  {
    id: "warm",
    name: "Warm tape",
    patch: {
      low: 2,
      mid: -1,
      high: -2,
      delay: 8,
      reverb: 10,
      chorus: 4,
      compressor: 20,
      drive: 18,
      filterCutoff: 14000,
      filterResonance: 0.8,
    },
  },
  {
    id: "lofi",
    name: "Lo-fi",
    patch: {
      low: 1.5,
      mid: -2,
      high: -7,
      delay: 4,
      reverb: 8,
      chorus: 18,
      compressor: 25,
      drive: 32,
      filterCutoff: 3600,
      filterResonance: 2.5,
    },
  },
  {
    id: "wide",
    name: "Wide chorus",
    patch: {
      low: 0,
      mid: 0,
      high: 1,
      delay: 12,
      reverb: 18,
      chorus: 35,
      compressor: 15,
      drive: 0,
      filterCutoff: 20000,
      filterResonance: 0.7,
    },
  },
  {
    id: "punch",
    name: "Punch",
    patch: {
      low: 2,
      mid: 1,
      high: 1,
      delay: 0,
      reverb: 4,
      chorus: 0,
      compressor: 55,
      drive: 12,
      filterCutoff: 18000,
      filterResonance: 0.9,
    },
  },
];
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
    let previousValue = base * (first.value / 100);
    gain.gain.setValueAtTime(previousValue, when);
    for (const point of automation) {
      if (point.time <= elapsed) continue;
      const at = Math.max(when + 0.001, when + (point.time - elapsed));
      const nextValue = base * (point.value / 100);
      if (point.curve === "exponential" && previousValue > 0 && nextValue > 0) {
        gain.gain.exponentialRampToValueAtTime(nextValue, at);
      } else {
        gain.gain.linearRampToValueAtTime(nextValue, at);
      }
      previousValue = nextValue;
    }
    return;
  }
  const fadeIn = Math.min(lane.fadeIn, length / 2);
  const fadeOut = Math.min(lane.fadeOut, length / 2);
  if (fadeIn > 0 && elapsed < fadeIn) {
    const startLevel = base * (elapsed / fadeIn);
    if (lane.fadeInCurve === "exponential") {
      gain.gain.setValueAtTime(Math.max(0.0001, startLevel), when);
      gain.gain.exponentialRampToValueAtTime(
        Math.max(0.0001, base),
        when + (fadeIn - elapsed)
      );
    } else {
      gain.gain.setValueAtTime(startLevel, when);
      gain.gain.linearRampToValueAtTime(base, when + (fadeIn - elapsed));
    }
  } else {
    gain.gain.setValueAtTime(base, when);
  }
  if (fadeOut > 0) {
    gain.gain.setValueAtTime(base, when + Math.max(0, length - fadeOut));
    if (lane.fadeOutCurve === "exponential") {
      gain.gain.exponentialRampToValueAtTime(0.0001, when + length);
    } else {
      gain.gain.linearRampToValueAtTime(0, when + length);
    }
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

function driveCurve(amount: number): Float32Array<ArrayBuffer> {
  const samples = 1024;
  const curve = new Float32Array(samples);
  const drive = 1 + clamp(amount, 0, 1) * 24;
  for (let index = 0; index < samples; index += 1) {
    const x = (index / (samples - 1)) * 2 - 1;
    curve[index] = Math.tanh(x * drive);
  }
  return curve as Float32Array<ArrayBuffer>;
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
  shaper.curve = driveCurve(amount);
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

function findImageUrl(value: unknown, allowAnyHttpUrl = false): string | null {
  if (typeof value === "string") {
    if (!/^https?:\/\//i.test(value)) return null;
    return allowAnyHttpUrl || /image|art|cover|jpg|jpeg|png|webp/i.test(value)
      ? value
      : null;
  }
  if (Array.isArray(value)) {
    for (const item of value) {
      const found = findImageUrl(item, allowAnyHttpUrl);
      if (found) return found;
    }
    return null;
  }
  if (value && typeof value === "object") {
    const record = value as Record<string, unknown>;
    for (const key of ["image_url", "imageUrl", "url", "image_large_url", "imageLargeUrl"]) {
      const found = findImageUrl(record[key], true);
      if (found) return found;
    }
    for (const item of Object.values(record)) {
      const found = findImageUrl(item, allowAnyHttpUrl);
      if (found) return found;
    }
  }
  return null;
}

type StudioLyricLine = {
  start: number;
  end: number;
  text: string;
};

function studioLyricsToLines(lyrics: StudioLyrics | null): StudioLyricLine[] {
  if (!lyrics) return [];
  const words: Array<{ word: string; start: number; end: number }> = [];
  for (const item of lyrics.aligned_words ?? []) {
    const word = String(item.word ?? item.text ?? "").trim();
    const start = Number(item.start_s ?? item.start);
    const end = Number(item.end_s ?? item.end);
    if (!word || !Number.isFinite(start)) continue;
    words.push({
      word,
      start,
      end: Number.isFinite(end) ? end : start,
    });
  }
  if (!words.length) {
    return String(lyrics.lyrics || "")
      .split(/\r?\n/)
      .map((line) => line.trim())
      .filter(Boolean)
      .map((text) => ({ start: 0, end: 0, text }));
  }
  const lines: StudioLyricLine[] = [];
  let current: Array<{ word: string; start: number; end: number }> = [];
  const flush = () => {
    if (!current.length) return;
    let text = "";
    for (const item of current) {
      const separator = !text
        ? ""
        : /^[.,!?;:)\]}%]/.test(item.word)
          ? ""
          : " ";
      text += `${separator}${item.word}`;
    }
    lines.push({
      start: current[0].start,
      end: current[current.length - 1].end,
      text: text.trim(),
    });
    current = [];
  };
  for (const word of words) {
    const previous = current[current.length - 1];
    if (previous && (word.start - previous.end > 1.2 || current.length >= 12)) {
      flush();
    }
    current.push(word);
  }
  flush();
  return lines;
}

function midiVlq(value: number): number[] {
  let buffer = Math.max(0, Math.floor(value)) & 0x7f;
  const out: number[] = [];
  let remaining = Math.max(0, Math.floor(value));
  while ((remaining >>= 7)) {
    buffer <<= 8;
    buffer |= (remaining & 0x7f) | 0x80;
  }
  while (true) {
    out.push(buffer & 0xff);
    if (buffer & 0x80) buffer >>= 8;
    else break;
  }
  return out;
}

function midiUint16(value: number): number[] {
  const safe = Math.max(0, Math.min(0xffff, Math.floor(value)));
  return [(safe >> 8) & 0xff, safe & 0xff];
}

function midiUint32(value: number): number[] {
  const safe = Math.max(0, Math.min(0xffffffff, Math.floor(value)));
  return [
    (safe >>> 24) & 0xff,
    (safe >>> 16) & 0xff,
    (safe >>> 8) & 0xff,
    safe & 0xff,
  ];
}

function midiMeta(type: number, data: number[]): number[] {
  return [0xff, type, ...midiVlq(data.length), ...data];
}

function midiTrackChunk(events: Array<{ delta: number; bytes: number[] }>): number[] {
  const body: number[] = [];
  for (const event of events) {
    body.push(...midiVlq(event.delta), ...event.bytes);
  }
  return [0x4d, 0x54, 0x72, 0x6b, ...midiUint32(body.length), ...body];
}

function buildMidiFile(lanes: Clip[], bpm: number, timeSignature: string): Blob {
  const safeBpm = Math.max(20, Math.min(300, Math.round(bpm || 90)));
  const ticksPerQuarter = 480;
  const secondsToTicks = (seconds: number) =>
    Math.max(0, Math.round((seconds * safeBpm * ticksPerQuarter) / 60));
  const [numeratorRaw, denominatorRaw] = String(timeSignature || "4/4")
    .split("/")
    .map((part) => Number(part));
  const numerator = Math.max(1, Math.min(32, Math.round(numeratorRaw || 4)));
  const denominator = Math.max(1, Math.min(32, Math.round(denominatorRaw || 4)));
  const midiLanes = lanes.filter((lane) => (lane.midiNotes ?? []).length);
  const encoder = new TextEncoder();

  const header = [
    0x4d, 0x54, 0x68, 0x64,
    0x00, 0x00, 0x00, 0x06,
    0x00, 0x01,
    ...midiUint16(midiLanes.length + 1),
    ...midiUint16(ticksPerQuarter),
  ];

  const tempo = Math.round(60_000_000 / safeBpm);
  const tempoBytes = [
    (tempo >> 16) & 0xff,
    (tempo >> 8) & 0xff,
    tempo & 0xff,
  ];
  const tempoEvents: Array<{ delta: number; bytes: number[] }> = [
    { delta: 0, bytes: midiMeta(0x51, tempoBytes) },
    {
      delta: 0,
      bytes: midiMeta(0x58, [
        numerator,
        Math.max(0, Math.min(7, Math.round(Math.log2(denominator)))),
        24,
        8,
      ]),
    },
    {
      delta: 0,
      bytes: midiMeta(0x03, Array.from(encoder.encode("Tempo"))),
    },
    { delta: 0, bytes: [0xff, 0x2f, 0x00] },
  ];

  const chunks = [header, midiTrackChunk(tempoEvents)];
  midiLanes.forEach((lane, index) => {
    const channel = index >= 9 ? (index + 1) % 16 : index % 16;
    const program =
      lane.instrument === "sawtooth" ? 81 : lane.instrument === "sine" ? 80 : 82;
    const events: Array<{
      tick: number;
      kind: 0 | 1;
      pitch: number;
      velocity: number;
    }> = [];
    for (const note of lane.midiNotes ?? []) {
      const pitch = Math.max(0, Math.min(127, Math.round(note.pitch)));
      const onTick = secondsToTicks(lane.start + note.time);
      const offTick = Math.max(onTick + 1, secondsToTicks(lane.start + note.time + note.duration));
      events.push({
        tick: onTick,
        kind: 1,
        pitch,
        velocity: Math.max(1, Math.min(127, Math.round(note.velocity * 127))),
      });
      events.push({ tick: offTick, kind: 0, pitch, velocity: 0 });
    }
    events.sort((a, b) => a.tick - b.tick || a.kind - b.kind || a.pitch - b.pitch);
    let previousTick = 0;
    let lastTick = 0;
    const encoded: Array<{ delta: number; bytes: number[] }> = [
      {
        delta: 0,
        bytes: midiMeta(0x03, Array.from(encoder.encode(lane.title || `MIDI ${index + 1}`))),
      },
      { delta: 0, bytes: [0xc0 | channel, program] },
    ];
    for (const event of events) {
      const delta = Math.max(0, event.tick - previousTick);
      previousTick = event.tick;
      lastTick = Math.max(lastTick, event.tick);
      encoded.push({
        delta,
        bytes:
          event.kind === 1
            ? [0x90 | channel, event.pitch, event.velocity]
            : [0x80 | channel, event.pitch, 0],
      });
    }
    encoded.push({ delta: Math.max(0, lastTick - previousTick), bytes: [0xff, 0x2f, 0x00] });
    chunks.push(midiTrackChunk(encoded));
  });

  return new Blob([new Uint8Array(chunks.flat())], { type: "audio/midi" });
}

type ParsedMidiNote = {
  time: number;
  pitch: number;
  duration: number;
  velocity: number;
};

type ParsedMidiTrack = {
  name: string;
  program: number;
  notes: ParsedMidiNote[];
};

type ParsedMidiFile = {
  bpm: number;
  timeSignature: string;
  tracks: ParsedMidiTrack[];
};

function parseMidiFile(buffer: ArrayBuffer): ParsedMidiFile {
  const bytes = new Uint8Array(buffer);
  let offset = 0;
  const fail = (message = "Invalid MIDI file.") => {
    throw new Error(message);
  };
  const u8 = () => {
    if (offset >= bytes.length) fail();
    return bytes[offset++] ?? 0;
  };
  const u16 = () => (u8() << 8) | u8();
  const u32 = () =>
    u8() * 0x1000000 + (u8() << 16) + (u8() << 8) + u8();
  const readVar = () => {
    let value = 0;
    for (let index = 0; index < 4; index += 1) {
      const byte = u8();
      value = (value << 7) | (byte & 0x7f);
      if (!(byte & 0x80)) return value;
    }
    fail("Invalid MIDI variable-length value.");
    return 0;
  };
  const ascii = (length: number) =>
    Array.from({ length }, () => String.fromCharCode(u8())).join("");

  if (ascii(4) !== "MThd") fail("Missing MIDI header.");
  const headerLength = u32();
  if (headerLength < 6) fail("Invalid MIDI header length.");
  const format = u16();
  if (format === 2) fail("MIDI format 2 is not supported.");
  const trackCount = u16();
  const division = u16();
  if (division & 0x8000) fail("SMPTE MIDI timing is not supported.");
  if (headerLength > 6) offset += headerLength - 6;

  const tempos: Array<{ tick: number; us: number }> = [];
  const rawTracks: Array<{
    name: string;
    program: number;
    notes: Array<{
      startTick: number;
      endTick: number;
      pitch: number;
      velocity: number;
    }>;
  }> = [];
  let timeSignature = "4/4";

  for (let trackIndex = 0; trackIndex < trackCount; trackIndex += 1) {
    if (offset + 8 > bytes.length || ascii(4) !== "MTrk") {
      fail("Missing MIDI track chunk.");
    }
    const trackLength = u32();
    const trackEnd = offset + trackLength;
    if (trackEnd > bytes.length) fail("Truncated MIDI track.");

    let tick = 0;
    let runningStatus = 0;
    let name = "";
    let program = 0;
    const active = new Map<
      string,
      { tick: number; pitch: number; velocity: number }
    >();
    const notes: Array<{
      startTick: number;
      endTick: number;
      pitch: number;
      velocity: number;
    }> = [];

    while (offset < trackEnd) {
      tick += readVar();
      let status = bytes[offset] ?? 0;
      if (status < 0x80) {
        status = runningStatus;
      } else {
        offset += 1;
        if (status < 0xf0) runningStatus = status;
      }
      if (!status) fail("Missing MIDI running status.");

      if (status === 0xff) {
        const type = u8();
        const length = readVar();
        const data = bytes.slice(offset, offset + length);
        offset += length;
        if (type === 0x03) {
          name = new TextDecoder().decode(data).trim();
        } else if (type === 0x51 && length >= 3) {
          tempos.push({
            tick,
            us: ((data[0] ?? 0) << 16) | ((data[1] ?? 0) << 8) | (data[2] ?? 0),
          });
        } else if (type === 0x58 && length >= 2) {
          const numerator = data[0] ?? 4;
          const denominator = Math.max(1, Math.min(32, 2 ** (data[1] ?? 2)));
          timeSignature = `${numerator}/${denominator}`;
        }
        continue;
      }
      if (status === 0xf0 || status === 0xf7) {
        const length = readVar();
        offset += length;
        continue;
      }

      const high = status & 0xf0;
      const channel = status & 0x0f;
      const data1 = u8();
      const data2 = high === 0xc0 || high === 0xd0 ? 0 : u8();
      if (high === 0xc0) {
        program = data1;
      } else if (high === 0x90 && data2 > 0) {
        active.set(`${channel}:${data1}`, {
          tick,
          pitch: data1,
          velocity: data2,
        });
      } else if (high === 0x80 || (high === 0x90 && data2 === 0)) {
        const key = `${channel}:${data1}`;
        const started = active.get(key);
        if (started) {
          notes.push({
            startTick: started.tick,
            endTick: Math.max(tick, started.tick + 1),
            pitch: started.pitch,
            velocity: started.velocity,
          });
          active.delete(key);
        }
      }
    }
    offset = trackEnd;
    if (notes.length) {
      rawTracks.push({
        name: name || `MIDI ${trackIndex + 1}`,
        program,
        notes,
      });
    }
  }

  if (!tempos.some((tempo) => tempo.tick === 0)) {
    tempos.push({ tick: 0, us: 500000 });
  }
  tempos.sort((a, b) => a.tick - b.tick);
  const initialTempo =
    [...tempos].reverse().find((tempo) => tempo.tick === 0)?.us ?? 500000;
  const safeDivision = Math.max(1, division);
  const ticksToSeconds = (targetTick: number) => {
    let seconds = 0;
    let lastTick = 0;
    let currentTempo = initialTempo;
    for (const tempo of tempos) {
      if (tempo.tick > targetTick) break;
      seconds += ((tempo.tick - lastTick) * currentTempo) / (safeDivision * 1_000_000);
      lastTick = tempo.tick;
      currentTempo = tempo.us;
    }
    seconds +=
      ((targetTick - lastTick) * currentTempo) / (safeDivision * 1_000_000);
    return seconds;
  };

  const tracks = rawTracks.map((track) => ({
    name: track.name,
    program: track.program,
    notes: track.notes.map((note) => {
      const start = ticksToSeconds(note.startTick);
      const end = ticksToSeconds(note.endTick);
      return {
        time: Number(start.toFixed(3)),
        pitch: note.pitch,
        duration: Math.max(0.05, Number((end - start).toFixed(3))),
        velocity: Math.max(0.05, Math.min(1, note.velocity / 127)),
      };
    }),
  }));

  return {
    bpm: Math.max(20, Math.min(300, Math.round(60_000_000 / initialTempo))),
    timeSignature,
    tracks,
  };
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
  const [masterCompressor, setMasterCompressor] = useState(0);
  const [masterDrive, setMasterDrive] = useState(0);
  const [masterLow, setMasterLow] = useState(0);
  const [masterMid, setMasterMid] = useState(0);
  const [masterHigh, setMasterHigh] = useState(0);
  const [masterEqOpen, setMasterEqOpen] = useState(false);
  const [masterMeter, setMasterMeter] = useState(0);
  const [playhead, setPlayhead] = useState(0);
  const [playing, setPlaying] = useState(false);
  const [audioLoading, setAudioLoading] = useState(false);
  const [audioError, setAudioError] = useState("");
  const [exporting, setExporting] = useState(false);
  const [exportError, setExportError] = useState("");
  const [importing, setImporting] = useState(false);
  const [importError, setImportError] = useState("");
  const [midiImporting, setMidiImporting] = useState(false);
  const [midiImportError, setMidiImportError] = useState("");
  const [recording, setRecording] = useState(false);
  const [countIn, setCountIn] = useState(false);
  const [countInBusy, setCountInBusy] = useState(false);
  const [recordCountdown, setRecordCountdown] = useState(0);
  const tapTimesRef = useRef<number[]>([]);
  const [recordSeconds, setRecordSeconds] = useState(0);
  const [recordError, setRecordError] = useState("");
  const [exportFormat, setExportFormat] = useState<"wav" | "mp3">("wav");
  const [exportRange, setExportRange] = useState<"full" | "loop">("full");
  const [loop, setLoop] = useState(false);
  const [loopStart, setLoopStart] = useState(0);
  const [loopEnd, setLoopEnd] = useState(60);
  const [markers, setMarkers] = useState<TimelineMarker[]>([]);
  const [selectedMidiNoteId, setSelectedMidiNoteId] = useState<string | null>(null);
  const [midiChordMode, setMidiChordMode] = useState<"off" | "major" | "minor">("off");
  const [midiArpMode, setMidiArpMode] = useState<"off" | "up" | "down">("off");
  const [midiStatus, setMidiStatus] = useState("");
  const [midiRecordArmed, setMidiRecordArmed] = useState(false);
  const [takesBusy, setTakesBusy] = useState(false);
  const [takesError, setTakesError] = useState("");
  const [mixClipboard, setMixClipboard] = useState<Partial<Clip> | null>(null);
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
  const [projectSearch, setProjectSearch] = useState("");
  const [projectSort, setProjectSort] = useState<"updated" | "title">("updated");
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
  const [shareDays, setShareDays] = useState(7);
  const [shareId, setShareId] = useState<string | null>(null);
  const [mashupOpen, setMashupOpen] = useState(false);
  const [mashupSelection, setMashupSelection] = useState<string[]>([]);
  const [mashupPrompt, setMashupPrompt] = useState("");
  const [mashupError, setMashupError] = useState("");
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
  const [inspectorTab, setInspectorTab] = useState<"clip" | "mix" | "lyrics" | "ai">("clip");
  const [lyrics, setLyrics] = useState<StudioLyrics | null>(null);
  const [lyricsLoading, setLyricsLoading] = useState(false);
  const [lyricsError, setLyricsError] = useState("");
  const lyricsCacheRef = useRef<Map<string, StudioLyrics>>(new Map());
  const [personas, setPersonas] = useState<StudioPersona[]>([]);
  const [personasBusy, setPersonasBusy] = useState(false);
  const [personasError, setPersonasError] = useState("");
  const [personasStatus, setPersonasStatus] = useState("");
  const [personaName, setPersonaName] = useState("");
  const [selectedPersonaId, setSelectedPersonaId] = useState("");
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
  const midiAccessRef = useRef<MIDIAccess | null>(null);
  const midiInstrumentRef = useRef<NonNullable<Clip["instrument"]>>("triangle");
  const midiRecordArmedRef = useRef(false);
  const selectedLaneRef = useRef<Clip | null>(null);
  const masterGainRef = useRef<GainNode | null>(null);
  const masterLimiterRef = useRef<DynamicsCompressorNode | null>(null);
  const masterEqRef = useRef<{ low: BiquadFilterNode; mid: BiquadFilterNode; high: BiquadFilterNode } | null>(null);
  const masterDriveRef = useRef<WaveShaperNode | null>(null);
  const analyserRef = useRef<AnalyserNode | null>(null);
  const meterFrameRef = useRef(0);
  const buffersRef = useRef<Map<string, AudioBuffer>>(new Map());
  const sourcesRef = useRef<AudioScheduledSourceNode[]>([]);
  const nodesRef = useRef<Map<string, { gain: GainNode; panner: StereoPannerNode; low: BiquadFilterNode; mid: BiquadFilterNode; high: BiquadFilterNode; filter: BiquadFilterNode; delayWet: GainNode; reverbWet: GainNode }>>(new Map());
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
    setSelectedMidiNoteId(null);
  }, [selected]);

  useEffect(() => {
    if (inspectorTab !== "lyrics") return;
    void loadLyrics();
  }, [inspectorTab, selected]);

  useEffect(() => {
    if (!user) return;
    void refreshPersonas();
  }, [user?.id]);

  useEffect(() => {
    return () => {
      const access = midiAccessRef.current;
      if (!access) return;
      access.onstatechange = null;
      access.inputs.forEach((input) => {
        input.onmidimessage = null;
      });
    };
  }, []);

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
        fadeInCurve: lane.fadeInCurve === "exponential" ? "exponential" : "linear",
        fadeOutCurve: lane.fadeOutCurve === "exponential" ? "exponential" : "linear",
        low: Number.isFinite(lane.low) ? clamp(Number(lane.low), -12, 12) : 0,
        mid: Number.isFinite(lane.mid) ? clamp(Number(lane.mid), -12, 12) : 0,
        high: Number.isFinite(lane.high) ? clamp(Number(lane.high), -12, 12) : 0,
        delay: Number.isFinite(lane.delay) ? clamp(Number(lane.delay), 0, 100) : 0,
        reverb: Number.isFinite(lane.reverb) ? clamp(Number(lane.reverb), 0, 100) : 0,
        chorus: Number.isFinite(lane.chorus) ? clamp(Number(lane.chorus), 0, 100) : 0,
        compressor: Number.isFinite(lane.compressor) ? clamp(Number(lane.compressor), 0, 100) : 0,
        drive: Number.isFinite(lane.drive) ? clamp(Number(lane.drive), 0, 100) : 0,
        filterCutoff: Number.isFinite(lane.filterCutoff) ? clamp(Number(lane.filterCutoff), 100, 20000) : 20000,
        filterResonance: Number.isFinite(lane.filterResonance) ? clamp(Number(lane.filterResonance), 0.1, 12) : 0.7,
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
                curve:
                  (point.curve === "exponential"
                    ? "exponential"
                    : "linear") as AutomationPoint["curve"],
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
    if (Number.isFinite(saved.masterCompressor)) {
      setMasterCompressor(clamp(Number(saved.masterCompressor), 0, 100));
    }
    if (Number.isFinite(saved.masterDrive)) setMasterDrive(clamp(Number(saved.masterDrive), 0, 100));
    if (Number.isFinite(saved.masterLow)) setMasterLow(clamp(Number(saved.masterLow), -12, 12));
    if (Number.isFinite(saved.masterMid)) setMasterMid(clamp(Number(saved.masterMid), -12, 12));
    if (Number.isFinite(saved.masterHigh)) setMasterHigh(clamp(Number(saved.masterHigh), -12, 12));
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
              masterCompressor: Number.isFinite(data.masterCompressor) ? Number(data.masterCompressor) : 0,
              masterDrive: Number.isFinite(data.masterDrive) ? Number(data.masterDrive) : 0,
              masterLow: Number.isFinite(data.masterLow) ? Number(data.masterLow) : 0,
              masterMid: Number.isFinite(data.masterMid) ? Number(data.masterMid) : 0,
              masterHigh: Number.isFinite(data.masterHigh) ? Number(data.masterHigh) : 0,
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
              masterCompressor: Number.isFinite(data.masterCompressor) ? Number(data.masterCompressor) : 0,
              masterDrive: Number.isFinite(data.masterDrive) ? Number(data.masterDrive) : 0,
              masterLow: Number.isFinite(data.masterLow) ? Number(data.masterLow) : 0,
              masterMid: Number.isFinite(data.masterMid) ? Number(data.masterMid) : 0,
              masterHigh: Number.isFinite(data.masterHigh) ? Number(data.masterHigh) : 0,
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
      const payload: StoredSession = { name: sessionName, bpm, timeSignature, gridDivision, zoom, master, masterCompressor, masterDrive, masterLow, masterMid, masterHigh, loopStart, loopEnd, markers, lanes };
      window.localStorage.setItem(storageKey, JSON.stringify(payload));
      setSavedAt(new Date());
    }, 350);
    return () => window.clearTimeout(timer);
  }, [loaded, user, storageKey, sessionName, bpm, timeSignature, gridDivision, zoom, master, masterCompressor, masterDrive, masterLow, masterMid, masterHigh, loopStart, loopEnd, markers, lanes]);

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
        const data: StudioProjectData = { lanes, gridDivision, loopStart, loopEnd, markers, zoom, master, masterCompressor, masterDrive, masterLow, masterMid, masterHigh };
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
  }, [loaded, user, projectId, sharedToken, sessionName, bpm, timeSignature, gridDivision, zoom, master, masterCompressor, masterDrive, masterLow, masterMid, masterHigh, loopStart, loopEnd, markers, lanes]);

  async function openProjects() {
    setProjectsOpen(true);
    setProjectSearch("");
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
              masterCompressor: Number.isFinite(data.masterCompressor) ? Number(data.masterCompressor) : 0,
              masterDrive: Number.isFinite(data.masterDrive) ? Number(data.masterDrive) : 0,
              masterLow: Number.isFinite(data.masterLow) ? Number(data.masterLow) : 0,
              masterMid: Number.isFinite(data.masterMid) ? Number(data.masterMid) : 0,
              masterHigh: Number.isFinite(data.masterHigh) ? Number(data.masterHigh) : 0,
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

  function exportProjectJson() {
    const payload: StoredSession = {
      name: sessionName,
      bpm,
      timeSignature,
      gridDivision,
      zoom,
      master,
      masterCompressor,
      masterDrive,
      masterLow,
      masterMid,
      masterHigh,
      loopStart,
      loopEnd,
      markers,
      lanes,
    };
    const safeName = (sessionName || "camxora-project").replace(/[\\/:*?"<>|]+/g, "-");
    saveBlob(
      new Blob([JSON.stringify(payload, null, 2)], { type: "application/json" }),
      `${safeName}.camxora.json`
    );
  }

  function exportMidiFile() {
    if (!hasMidiLanes) return;
    const safeName = (sessionName || "camxora-midi").replace(/[\\/:*?"<>|]+/g, "-");
    saveBlob(buildMidiFile(lanes, bpm, timeSignature), `${safeName}.mid`);
  }

  async function importProjectJson(file: File) {
    try {
      const payload = JSON.parse(await file.text()) as StoredSession;
      if (!Array.isArray(payload.lanes)) {
        throw new Error("This file does not contain a Studio project.");
      }
      applySession(payload, null);
      setSharedToken(null);
      setProjectId(null);
      setCloudState("local");
      setHistory([]);
      setFuture([]);
      setActionsOpen(false);
    } catch (cause) {
      setCloudError(cause instanceof Error ? cause.message : "Could not import project.");
    }
  }

  async function duplicateProject(project: { id: string; title: string }) {
    if (projectsBusy) return;
    setProjectsBusy(true);
    setProjectsError("");
    try {
      const copy = await forkStudioProject(project.id);
      setProjectList((current) => [copy, ...current]);
    } catch (cause) {
      setProjectsError(
        cause instanceof Error ? cause.message : "Could not duplicate project."
      );
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
        data: { lanes, gridDivision, loopStart, loopEnd, markers, zoom, master, masterCompressor, masterDrive, masterLow, masterMid, masterHigh },
      });
      const share = await createStudioProjectShare(projectId, shareDays, sharePermission);
      setShareId(share.id);
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

  async function revokeShare() {
    if (!projectId || !shareId) return;
    if (!window.confirm("Revoke this share link? Anyone using it will lose access.")) return;
    try {
      await revokeStudioProjectShare(projectId, shareId);
      setShareUrl("");
      setShareId(null);
    } catch (cause) {
      setShareError(cause instanceof Error ? cause.message : "Could not revoke share link.");
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
        data: { lanes, gridDivision, loopStart, loopEnd, markers, zoom, master, masterCompressor, masterDrive, masterLow, masterMid, masterHigh },
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
              masterCompressor: Number.isFinite(data.masterCompressor) ? Number(data.masterCompressor) : 0,
              masterDrive: Number.isFinite(data.masterDrive) ? Number(data.masterDrive) : 0,
              masterLow: Number.isFinite(data.masterLow) ? Number(data.masterLow) : 0,
              masterMid: Number.isFinite(data.masterMid) ? Number(data.masterMid) : 0,
              masterHigh: Number.isFinite(data.masterHigh) ? Number(data.masterHigh) : 0,
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

  function tapTempo() {
    const now = performance.now();
    const taps = tapTimesRef.current.filter((time) => now - time < 3000);
    taps.push(now);
    tapTimesRef.current = taps.slice(-8);
    if (taps.length >= 2) {
      const intervals = taps.slice(1).map((time, index) => time - taps[index]);
      const average = intervals.reduce((sum, value) => sum + value, 0) / intervals.length;
      if (average > 0) setBpm(clamp(Math.round(60000 / average), 40, 220));
    }
  }

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
  midiInstrumentRef.current = selectedLane?.instrument ?? "triangle";
  selectedLaneRef.current = selectedLane;
  midiRecordArmedRef.current = midiRecordArmed;
  const canUseAiEdits = Boolean(
    selectedLane && (selectedLane.variant === "ok" || selectedLane.variant === "alt")
  );
  const activeInspectorTab = inspectorTab === "ai" && !canUseAiEdits ? "clip" : inspectorTab;
  const lyricLines = useMemo(() => studioLyricsToLines(lyrics), [lyrics]);
  const hasMidiLanes = useMemo(
    () => lanes.some((lane) => (lane.midiNotes ?? []).length > 0),
    [lanes]
  );
  const filteredProjects = useMemo(() => {
    const query = projectSearch.trim().toLowerCase();
    const filtered = query
      ? projectList.filter((project) =>
          project.title.toLowerCase().includes(query)
        )
      : projectList;
    return [...filtered].sort((a, b) => {
      if (projectSort === "title") return a.title.localeCompare(b.title);
      return (
        new Date(b.updated_at ?? 0).getTime() -
        new Date(a.updated_at ?? 0).getTime()
      );
    });
  }, [projectList, projectSearch, projectSort]);
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

  const updateVolumeAutomationPoint = useCallback(
    (pointId: string, patch: Partial<AutomationPoint>) => {
      if (!selectedLane) return;
      updateLane(selectedLane.id, {
        automation: (selectedLane.automation ?? []).map((point) =>
          point.id === pointId ? { ...point, ...patch } : point
        ),
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

  const updateMeter = useCallback(() => {
    const analyser = analyserRef.current;
    if (!analyser) return;
    const data = new Uint8Array(analyser.fftSize);
    analyser.getByteTimeDomainData(data);
    let sum = 0;
    for (const value of data) {
      const centered = (value - 128) / 128;
      sum += centered * centered;
    }
    const rms = Math.sqrt(sum / data.length);
    setMasterMeter(clamp(rms * 3.2, 0, 1));
  }, []);

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
    setMasterMeter(0);
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
    if (masterLimiterRef.current) {
      const amount = masterCompressor / 100;
      masterLimiterRef.current.threshold.value = -3 - amount * 12;
      masterLimiterRef.current.ratio.value = 20;
      masterLimiterRef.current.knee.value = amount * 6;
    }
    if (masterDriveRef.current) {
      masterDriveRef.current.curve = driveCurve(masterDrive / 100);
    }
    if (masterEqRef.current) {
      masterEqRef.current.low.gain.value = masterLow;
      masterEqRef.current.mid.gain.value = masterMid;
      masterEqRef.current.high.gain.value = masterHigh;
    }
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
      node.filter.frequency.value = clamp(lane.filterCutoff ?? 20000, 100, 20000);
      node.filter.Q.value = clamp(lane.filterResonance ?? 0.7, 0.1, 12);
      node.delayWet.gain.value = lane.delay / 100;
      node.reverbWet.gain.value = lane.reverb / 100;
    }
  }, [lanes, master, masterCompressor, masterDrive, masterLow, masterMid, masterHigh]);

  const ensureAudioContext = useCallback((): AudioContext => {
    if (audioCtxRef.current) return audioCtxRef.current;
    const context = new AudioContext();
    const gain = context.createGain();
    gain.gain.value = master / 100;
    const masterShaper = context.createWaveShaper();
    masterShaper.curve = driveCurve(masterDrive / 100);
    masterShaper.oversample = "4x";
    const low = context.createBiquadFilter();
    low.type = "lowshelf";
    low.frequency.value = 120;
    low.gain.value = masterLow;
    const mid = context.createBiquadFilter();
    mid.type = "peaking";
    mid.frequency.value = 1000;
    mid.Q.value = 0.8;
    mid.gain.value = masterMid;
    const high = context.createBiquadFilter();
    high.type = "highshelf";
    high.frequency.value = 6000;
    high.gain.value = masterHigh;
    const limiter = context.createDynamicsCompressor();
    const amount = masterCompressor / 100;
    limiter.threshold.value = -3 - amount * 12;
    limiter.knee.value = amount * 6;
    limiter.ratio.value = 20;
    limiter.attack.value = 0.003;
    limiter.release.value = 0.1;
    gain.connect(masterShaper);
    masterShaper.connect(low);
    low.connect(mid);
    mid.connect(high);
    high.connect(limiter);
    const analyser = context.createAnalyser();
    analyser.fftSize = 256;
    limiter.connect(analyser);
    analyser.connect(context.destination);
    audioCtxRef.current = context;
    masterGainRef.current = gain;
    masterLimiterRef.current = limiter;
    masterEqRef.current = { low, mid, high };
    masterDriveRef.current = masterShaper;
    analyserRef.current = analyser;
    return context;
  }, [master, masterCompressor, masterDrive, masterLow, masterMid, masterHigh]);

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
          if (meterFrameRef.current++ % 6 === 0) updateMeter();
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
          const filter = context.createBiquadFilter();
          filter.type = "lowpass";
          filter.frequency.value = clamp(lane.filterCutoff ?? 20000, 100, 20000);
          filter.Q.value = clamp(lane.filterResonance ?? 0.7, 0.1, 12);
          high.connect(filter);
          const chorusOut = context.createGain();
          connectTrackChorus(context, filter, chorusOut, lane, startWhen, remaining);
          const driveOut = context.createGain();
          connectTrackDrive(context, chorusOut, driveOut, lane);
          connectTrackDynamics(context, driveOut, gain, lane);
          gain.connect(panner);
          const fx = connectTrackFx(context, panner, masterGain, lane);
          scheduleClipGain(gain, lane.volume / 100, lane, from, startWhen, remaining);
          schedulePanAutomation(panner, lane, from, startWhen, remaining);
          source.start(startWhen, offset, remaining);
          sourcesRef.current.push(source);
          nodesRef.current.set(lane.id, { gain, panner, low, mid, high, filter, ...fx });
        }
        startedAtRef.current = startAt;
        startPlayheadRef.current = from;
        setPlaying(true);
        const tick = () => {
          const next = from + Math.max(0, context.currentTime - startAt);
          setPlayhead(Math.min(timelineDurationRef.current, next));
          if (meterFrameRef.current++ % 6 === 0) updateMeter();
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
    [ensureAudioContext, lanes, loadBuffer, scheduleMetronome, stopSources, updateMeter]
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

  async function runCountIn() {
    const context = ensureAudioContext();
    await context.resume();
    const beat = 60 / Math.max(40, bpm);
    const start = context.currentTime + 0.06;
    for (let index = 0; index < 4; index += 1) {
      const osc = context.createOscillator();
      const gain = context.createGain();
      const when = start + index * beat;
      osc.frequency.value = index === 0 ? 1600 : 1000;
      gain.gain.setValueAtTime(0.12, when);
      gain.gain.exponentialRampToValueAtTime(0.0001, when + 0.05);
      osc.connect(gain);
      gain.connect(context.destination);
      osc.start(when);
      osc.stop(when + 0.06);
    }
    for (let index = 4; index > 0; index -= 1) {
      setRecordCountdown(index);
      await new Promise((resolve) => window.setTimeout(resolve, beat * 1000));
    }
    setRecordCountdown(0);
  }

  async function startRecording() {
    if (recording || importing || countInBusy) return;
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
      setCountInBusy(true);
      if (countIn) await runCountIn();
      recorder.start(250);
      setCountInBusy(false);
      setRecording(true);
      setRecordSeconds(0);
      recordTimerRef.current = window.setInterval(
        () => setRecordSeconds((value) => value + 1),
        1000
      );
    } catch (cause) {
      recordStreamRef.current?.getTracks().forEach((track) => track.stop());
      recordStreamRef.current = null;
      setCountInBusy(false);
      setRecordCountdown(0);
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

  async function importMidiFile(file: File) {
    if (midiImporting) return;
    if (file.size > 5 * 1024 * 1024) {
      setMidiImportError("MIDI imports are limited to 5 MB.");
      return;
    }
    setMidiImporting(true);
    setMidiImportError("");
    try {
      const parsed = parseMidiFile(await file.arrayBuffer());
      if (!parsed.tracks.length) {
        throw new Error("The MIDI file contains no note events.");
      }
      const baseName = file.name.replace(/\.midi?$/i, "") || "Imported MIDI";
      const imported = parsed.tracks.map((track, index): Clip => {
        const midiNotes: MidiNote[] = track.notes.map((note) => ({
          id: makeId(),
          time: note.time,
          pitch: note.pitch,
          duration: note.duration,
          velocity: note.velocity,
        }));
        const duration = Math.max(
          4,
          ...midiNotes.map((note) => note.time + note.duration + 1)
        );
        return {
          id: makeId(),
          generationId: `midi-import:${makeId()}`,
          variant: "midi",
          title: track.name || `${baseName} ${index + 1}`,
          style: "Imported MIDI",
          color: COLORS[(lanes.length + index) % COLORS.length],
          image: null,
          start: 0,
          duration,
          offset: 0,
          fadeIn: 0,
          fadeOut: 0,
          automation: [],
          panAutomation: [],
          audioUrl: null,
          midiNotes,
          instrument:
            track.program >= 80
              ? "sawtooth"
              : track.program >= 32
                ? "triangle"
                : "sine",
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
      commitLanes([...lanes, ...imported]);
      setSelected(imported[0].id);
      setBpm(parsed.bpm);
      setTimeSignature(parsed.timeSignature);
    } catch (cause) {
      setMidiImportError(
        cause instanceof Error ? cause.message : "Could not import MIDI."
      );
    } finally {
      setMidiImporting(false);
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
    if (midiChordMode !== "off") {
      const intervals = midiChordMode === "major" ? [0, 4, 7] : [0, 3, 7];
      const targets = intervals
        .map((interval) => pitch + interval)
        .filter((target) => target >= 0 && target <= 127);
      const ordered = midiArpMode === "down" ? [...targets].reverse() : targets;
      const step = midiArpMode === "off" ? 0 : 0.5;
      const desired = ordered.map((target, index) => ({
        pitch: target,
        time: Number((time + index * step).toFixed(2)),
        duration: midiArpMode === "off" ? 0.45 : 0.4,
      }));
      const existing = desired.map((item) =>
        notes.find(
          (note) =>
            Math.abs(note.time - item.time) < 0.01 && note.pitch === item.pitch
        )
      );
      if (existing.every(Boolean)) {
        setSelectedMidiNoteId(existing[0]?.id ?? null);
        return;
      }
      const additions: MidiNote[] = [];
      desired.forEach((item, index) => {
        if (existing[index]) return;
        additions.push({
          id: makeId(),
          time: item.time,
          pitch: item.pitch,
          duration: item.duration,
          velocity: 0.8,
        });
      });
      invalidateMidi(selectedLane);
      updateLane(selectedLane.id, { midiNotes: [...notes, ...additions] });
      setSelectedMidiNoteId(additions[0]?.id ?? existing[0]?.id ?? null);
      return;
    }
    const existing = notes.find(
      (note) => Math.abs(note.time - time) < 0.01 && note.pitch === pitch
    );
    if (existing) {
      setSelectedMidiNoteId(existing.id);
      return;
    }
    const note: MidiNote = {
      id: makeId(),
      time,
      pitch,
      duration: 0.45,
      velocity: 0.8,
    };
    invalidateMidi(selectedLane);
    updateLane(selectedLane.id, { midiNotes: [...notes, note] });
    setSelectedMidiNoteId(note.id);
  }

  async function connectMidiInput() {
    if (!navigator.requestMIDIAccess) {
      setMidiStatus("Web MIDI is not available in this browser.");
      return;
    }
    setMidiStatus("Requesting MIDI access…");
    try {
      const access = await navigator.requestMIDIAccess();
      midiAccessRef.current = access;
      const attach = () => {
        const names: string[] = [];
        access.inputs.forEach((input) => {
          names.push(input.name || "MIDI input");
          input.onmidimessage = (event) => {
            if (!event.data || event.data.length < 3) return;
            const statusByte = event.data[0] ?? 0;
            const pitch = event.data[1] ?? 0;
            const velocity = event.data[2] ?? 0;
            const status = statusByte & 0xf0;
            if (status === 0x90 && velocity > 0) {
              previewMidiPitch(pitch, velocity / 127);
            }
          };
        });
        setMidiStatus(
          names.length
            ? `MIDI: ${names.join(", ")}`
            : "MIDI connected — no devices found."
        );
      };
      attach();
      access.onstatechange = attach;
    } catch {
      midiAccessRef.current = null;
      setMidiStatus("MIDI access was denied or failed.");
    }
  }

  function recordMidiNote(pitch: number, velocity = 0.8) {
    if (!midiRecordArmedRef.current) return;
    const lane = selectedLaneRef.current;
    if (!lane?.midiNotes) {
      setMidiStatus("Select a MIDI track before recording notes.");
      return;
    }
    const notes = lane.midiNotes;
    const time = Number(
      clamp(playheadRef.current - lane.start, 0, lane.duration).toFixed(2)
    );
    const existing = notes.find(
      (note) => Math.abs(note.time - time) < 0.04 && note.pitch === pitch
    );
    if (existing) {
      setSelectedMidiNoteId(existing.id);
      return;
    }
    const note: MidiNote = {
      id: makeId(),
      time,
      pitch,
      duration: 0.5,
      velocity: clamp(velocity, 0.05, 1),
    };
    invalidateMidi(lane);
    updateLane(lane.id, { midiNotes: [...notes, note] });
    setSelectedMidiNoteId(note.id);
    setMidiStatus(`Recorded ${midiNoteName(pitch)} at ${time.toFixed(2)}s.`);
  }

  function previewMidiPitch(pitch: number, velocity = 0.8) {
    recordMidiNote(pitch, velocity);
    const context = ensureAudioContext();
    const master = masterGainRef.current ?? context.destination;
    const now = context.currentTime;
    const oscillator = context.createOscillator();
    oscillator.type = midiInstrumentRef.current;
    oscillator.frequency.value = 440 * Math.pow(2, (pitch - 69) / 12);
    const gain = context.createGain();
    gain.gain.setValueAtTime(0.0001, now);
    gain.gain.exponentialRampToValueAtTime(0.18, now + 0.012);
    gain.gain.exponentialRampToValueAtTime(0.0001, now + 0.55);
    oscillator.connect(gain);
    gain.connect(master);
    oscillator.start(now);
    oscillator.stop(now + 0.58);
  }

  function updateMidiNote(noteId: string, patch: Partial<MidiNote>) {
    if (!selectedLane?.midiNotes) return;
    invalidateMidi(selectedLane);
    updateLane(selectedLane.id, {
      midiNotes: selectedLane.midiNotes.map((note) =>
        note.id === noteId ? { ...note, ...patch } : note
      ),
    });
  }

  function deleteMidiNote(noteId: string) {
    if (!selectedLane?.midiNotes) return;
    invalidateMidi(selectedLane);
    updateLane(selectedLane.id, {
      midiNotes: selectedLane.midiNotes.filter((note) => note.id !== noteId),
    });
    setSelectedMidiNoteId(null);
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

  async function addAlternateTake(lane: Clip) {
    if (takesBusy) return;
    if (
      lane.uploadId ||
      lane.midiNotes ||
      (lane.variant !== "ok" && lane.variant !== "alt")
    ) {
      setTakesError("Alternate takes are available for original generated clips.");
      return;
    }
    setTakesBusy(true);
    setTakesError("");
    try {
      const generations = await fetchGenerations(100);
      const generation = generations.find((item) => item.id === lane.generationId);
      const alternate = generation?.clips.find(
        (clip) =>
          clip.variant !== lane.variant &&
          Boolean(clip.audio_url || clip.download_url)
      );
      if (!alternate) {
        setTakesError("No alternate take was found for this clip.");
        return;
      }
      const existing = lanes.find(
        (item) =>
          item.generationId === lane.generationId &&
          item.variant === alternate.variant
      );
      if (existing) {
        setSelected(existing.id);
        setTakesError("That alternate take is already in the session.");
        return;
      }
      const copy: Clip = {
        ...lane,
        id: makeId(),
        variant: alternate.variant,
        title: alternate.title || generation?.title || lane.title,
        audioUrl: alternate.audio_url || alternate.download_url || lane.audioUrl,
        image: alternate.image_url || lane.image,
        duration: Math.max(
          MIN_CLIP,
          Number(alternate.duration_seconds || lane.duration)
        ),
        offset: 0,
        start: lane.start,
        fadeIn: 0,
        fadeOut: 0,
        automation: [],
        panAutomation: [],
        color: COLORS[lanes.length % COLORS.length],
      };
      commitLanes([...lanes, copy]);
      setSelected(copy.id);
    } catch (cause) {
      setTakesError(
        cause instanceof Error ? cause.message : "Could not load alternate take."
      );
    } finally {
      setTakesBusy(false);
    }
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

  function copyMixSettings(lane: Clip) {
    setMixClipboard({
      volume: lane.volume,
      pan: lane.pan,
      low: lane.low,
      mid: lane.mid,
      high: lane.high,
      delay: lane.delay,
      reverb: lane.reverb,
      chorus: lane.chorus,
      compressor: lane.compressor,
      drive: lane.drive,
      automation: lane.automation ?? [],
      panAutomation: lane.panAutomation ?? [],
    });
  }

  function pasteMixSettings(lane: Clip) {
    if (!mixClipboard) return;
    updateLane(lane.id, mixClipboard);
  }

  function applyMasterPreset(patch: MasterPresetPatch) {
    setMaster(patch.master);
    setMasterCompressor(patch.masterCompressor);
    setMasterDrive(patch.masterDrive);
    setMasterLow(patch.masterLow);
    setMasterMid(patch.masterMid);
    setMasterHigh(patch.masterHigh);
  }

  function resetMixSettings(lane: Clip) {
    updateLane(lane.id, {
      volume: 80,
      pan: 0,
      low: 0,
      mid: 0,
      high: 0,
      delay: 0,
      reverb: 0,
      chorus: 0,
      compressor: 0,
      drive: 0,
      automation: [],
      panAutomation: [],
    });
  }

  function moveLane(lane: Clip, direction: -1 | 1) {
    const index = lanes.findIndex((item) => item.id === lane.id);
    if (index < 0) return;
    const target = index + direction;
    if (target < 0 || target >= lanes.length) return;
    const next = [...lanes];
    [next[index], next[target]] = [next[target], next[index]];
    commitLanes(next);
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
    const masterAmount = masterCompressor / 100;
    limiter.threshold.value = -3 - masterAmount * 12;
    limiter.knee.value = masterAmount * 6;
    limiter.ratio.value = 20;
    limiter.attack.value = 0.003;
    limiter.release.value = 0.1;
    const masterShaper = offline.createWaveShaper();
    masterShaper.curve = driveCurve(masterDrive / 100);
    masterShaper.oversample = "4x";
    const masterLowFilter = offline.createBiquadFilter();
    masterLowFilter.type = "lowshelf";
    masterLowFilter.frequency.value = 120;
    masterLowFilter.gain.value = masterLow;
    const masterMidFilter = offline.createBiquadFilter();
    masterMidFilter.type = "peaking";
    masterMidFilter.frequency.value = 1000;
    masterMidFilter.Q.value = 0.8;
    masterMidFilter.gain.value = masterMid;
    const masterHighFilter = offline.createBiquadFilter();
    masterHighFilter.type = "highshelf";
    masterHighFilter.frequency.value = 6000;
    masterHighFilter.gain.value = masterHigh;
    masterGain.connect(masterShaper);
    masterShaper.connect(masterLowFilter);
    masterLowFilter.connect(masterMidFilter);
    masterMidFilter.connect(masterHighFilter);
    masterHighFilter.connect(limiter);
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
      const filter = offline.createBiquadFilter();
      filter.type = "lowpass";
      filter.frequency.value = clamp(lane.filterCutoff ?? 20000, 100, 20000);
      filter.Q.value = clamp(lane.filterResonance ?? 0.7, 0.1, 12);
      high.connect(filter);
      const chorusOut = offline.createGain();
      connectTrackChorus(offline, filter, chorusOut, lane, when, length);
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

  async function runCoverImage() {
    if (!selectedLane || editBusy) return;
    if (selectedLane.variant !== "ok" && selectedLane.variant !== "alt") {
      setEditError("Select an original generated clip first.");
      return;
    }
    if (!editPrompt.trim()) {
      setEditError("Describe the cover art you want first.");
      return;
    }
    setEditBusy(true);
    setEditError("");
    setEditStatus("Generating cover art?");
    try {
      let operation = await requestStudioCoverImage({
        taskId: selectedLane.generationId,
        variant: selectedLane.variant,
        prompt: editPrompt.trim(),
        projectId,
      });
      for (let attempt = 0; attempt < 80; attempt += 1) {
        if (["complete", "success", "error", "failed"].includes(operation.status.toLowerCase())) {
          break;
        }
        await new Promise((resolve) => window.setTimeout(resolve, 3000));
        operation = await getStudioOperation(operation.id);
        setEditStatus("Generating cover art?");
      }
      if (["error", "failed"].includes(operation.status.toLowerCase())) {
        throw new Error(operation.error_message || "Cover art generation failed.");
      }
      const imageUrl = findImageUrl(operation.result);
      if (!imageUrl) throw new Error("Cover art generation returned no image.");
      updateLane(selectedLane.id, { image: imageUrl });
      setEditStatus("Cover art updated");
    } catch (cause) {
      setEditError(cause instanceof Error ? cause.message : "Could not generate cover art.");
      setEditStatus("");
    } finally {
      setEditBusy(false);
    }
  }

  async function refreshPersonas() {
    setPersonasBusy(true);
    setPersonasError("");
    try {
      const next = await listStudioPersonas();
      setPersonas(next);
      setSelectedPersonaId((current) => {
        if (current && next.some((item) => item.provider_persona_id === current && item.status === "complete")) {
          return current;
        }
        return next.find((item) => item.status === "complete" && item.provider_persona_id)?.provider_persona_id ?? "";
      });
    } catch (cause) {
      setPersonasError(cause instanceof Error ? cause.message : "Could not load personas.");
    } finally {
      setPersonasBusy(false);
    }
  }

  async function createPersonaFromSelected() {
    if (!selectedLane || personasBusy) return;
    if (selectedLane.variant !== "ok" && selectedLane.variant !== "alt") {
      setPersonasError("Select an original generated clip first.");
      return;
    }
    const name = personaName.trim() || `${selectedLane.title} persona`;
    setPersonasBusy(true);
    setPersonasError("");
    setPersonasStatus("Creating persona…");
    try {
      const created = await createStudioPersona({
        taskId: selectedLane.generationId,
        name,
        styles: selectedLane.style,
        description: `Created from ${selectedLane.title}`,
        vocalStartS: selectedLane.offset,
        vocalEndS: selectedLane.offset + selectedLane.duration,
        variant: selectedLane.variant,
      });
      setPersonas((current) => [created, ...current]);
      setPersonaName("");
      setPersonasStatus("Persona submitted. Refresh shortly to use it.");
      window.setTimeout(() => void refreshPersonas(), 8000);
      window.setTimeout(() => void refreshPersonas(), 20000);
    } catch (cause) {
      setPersonasError(cause instanceof Error ? cause.message : "Could not create persona.");
      setPersonasStatus("");
    } finally {
      setPersonasBusy(false);
    }
  }

  async function loadLyrics(force = false) {
    const lane = selectedLane;
    if (!lane) return;
    if (lane.uploadId) {
      setLyrics(null);
      setLyricsError("Lyrics are available for generated clips, not uploaded audio.");
      return;
    }
    if (lane.variant !== "ok" && lane.variant !== "alt") {
      setLyrics(null);
      setLyricsError("Select an original generated clip to load its lyrics.");
      return;
    }
    const key = `${lane.generationId}:${lane.variant}`;
    const cached = lyricsCacheRef.current.get(key);
    if (cached && !force) {
      setLyrics(cached);
      setLyricsError("");
      return;
    }
    setLyricsLoading(true);
    setLyricsError("");
    try {
      const payload = await getStudioLyrics({
        taskId: lane.generationId,
        variant: lane.variant,
      });
      lyricsCacheRef.current.set(key, payload);
      setLyrics(payload);
    } catch (cause) {
      setLyrics(null);
      setLyricsError(cause instanceof Error ? cause.message : "Could not load lyrics.");
    } finally {
      setLyricsLoading(false);
    }
  }

  async function runStudioEdit(
    label: string,
    request: () => Promise<StudioOperation>,
    sourceLane: Clip | null = selectedLane,
    allowUpload = false
  ) {
    if (!sourceLane || editBusy) return;
    if (
      !allowUpload &&
      sourceLane.variant !== "ok" &&
      sourceLane.variant !== "alt"
    ) {
      setEditError("Select an original version before editing it.");
      return;
    }
    if (allowUpload && !sourceLane.uploadId) {
      setEditError("Select an uploaded audio clip first.");
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
      const next = operationClipsToLanes(operation.result?.clips, sourceLane, label);
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
      if (selectedLane.uploadId) {
        const uploadId = selectedLane.uploadId;
        setAiStatus("Extending the uploaded clip…");
        void runStudioEdit(
          "Upload extend",
          () =>
            requestStudioUploadExtend({
              uploadId,
              prompt: command,
              continueAt: selectedLane.offset + selectedLane.duration,
              title: selectedLane.title,
              tags: selectedLane.style,
              projectId,
            }),
          selectedLane,
          true
        );
        return;
      }
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
      if (selectedLane.uploadId) {
        const uploadId = selectedLane.uploadId;
        setAiStatus("Covering the uploaded clip…");
        void runStudioEdit(
          "Upload cover",
          () =>
            requestStudioUploadCover({
              uploadId,
              prompt: command,
              coverStartS: selectedLane.offset,
              coverEndS: selectedLane.offset + selectedLane.duration,
              title: selectedLane.title,
              tags: selectedLane.style,
              projectId,
            }),
          selectedLane,
          true
        );
        return;
      }
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

  function openMashup() {
    const eligible = lanes.filter(
      (lane) => lane.variant === "ok" || lane.variant === "alt"
    );
    if (eligible.length < 2) {
      setMashupError("Add at least two original generated tracks to mash up.");
      setMashupOpen(true);
      return;
    }
    setMashupSelection(eligible.slice(0, 2).map((lane) => lane.id));
    setMashupPrompt("");
    setMashupError("");
    setMashupOpen(true);
  }

  function toggleMashupLane(laneId: string) {
    setMashupSelection((current) => {
      if (current.includes(laneId)) return current.filter((id) => id !== laneId);
      if (current.length >= 2) return current;
      return [...current, laneId];
    });
  }

  async function createMashup() {
    const selectedClips = lanes.filter((lane) =>
      mashupSelection.includes(lane.id)
    );
    if (selectedClips.length < 2) {
      setMashupError("Select exactly two original generated tracks.");
      return;
    }
    setMashupOpen(false);
    await runStudioEdit(
      "Mashup",
      () =>
        requestStudioMashup({
          clips: selectedClips.map((lane) => ({
            taskId: lane.generationId,
            variant: lane.variant,
          })),
          prompt: mashupPrompt.trim(),
          projectId,
        }),
      selectedClips[0]
    );
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
          {recording || countInBusy ? (
            <button
              className={`btn btn-ghost studio-record-btn${recording ? " recording" : ""}`}
              type="button"
              onClick={recording ? stopRecording : undefined}
              disabled={countInBusy}
            >
              <Icon name={countInBusy ? "fa-hourglass-half" : "fa-stop"} />
              {countInBusy
                ? `Count-in ${recordCountdown}`
                : `${String(Math.floor(recordSeconds / 60)).padStart(2, "0")}:${String(recordSeconds % 60).padStart(2, "0")}`}
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
                  <button type="button" onClick={() => { setActionsOpen(false); exportProjectJson(); }}>
                    <Icon name="fa-download" /> Export project
                  </button>
                  <label>
                    <Icon name="fa-upload" /> Import project
                    <input
                      type="file"
                      accept="application/json,.json"
                      onChange={(event) => {
                        const file = event.currentTarget.files?.[0];
                        if (file) void importProjectJson(file);
                        event.currentTarget.value = "";
                      }}
                      hidden
                    />
                  </label>
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
                  <label>
                    <Icon name={midiImporting ? "fa-spinner" : "fa-music"} /> Import MIDI
                    <input
                      type="file"
                      accept=".mid,.midi,audio/midi,audio/x-midi"
                      disabled={midiImporting}
                      onChange={(event) => {
                        const file = event.currentTarget.files?.[0];
                        if (file) void importMidiFile(file);
                        event.currentTarget.value = "";
                        setActionsOpen(false);
                      }}
                      hidden
                    />
                  </label>
                  <button type="button" disabled={countInBusy} onClick={() => { setActionsOpen(false); void startRecording(); }}>
                    <Icon name="fa-microphone" /> Record
                  </button>
                  <button type="button" onClick={() => { setActionsOpen(false); setCountIn((value) => !value); }}>
                    <Icon name="fa-hourglass-half" /> Count-in: {countIn ? "On" : "Off"}
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
              disabled={!hasMidiLanes || exporting}
              onClick={exportMidiFile}
              title="Export MIDI tracks as a standard MIDI file"
            >
              <Icon name="fa-music" /> <span>MIDI</span>
            </button>
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
      {importError || recordError || midiImportError ? (
        <div className="studio-head-errors">
          {importError ? <small>{importError}</small> : null}
          {recordError ? <small>{recordError}</small> : null}
          {midiImportError ? <small>{midiImportError}</small> : null}
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
        <button className="studio-tap-tempo" type="button" onClick={tapTempo} title="Tap four times to set tempo">
          Tap
        </button>
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
                {(["clip", "mix", "lyrics"] as const).map((tab) => (
                  <button
                    key={tab}
                    className={activeInspectorTab === tab ? "active" : ""}
                    type="button"
                    role="tab"
                    aria-selected={activeInspectorTab === tab}
                    onClick={() => setInspectorTab(tab)}
                  >
                    {tab === "clip" ? "Clip" : tab === "mix" ? "Mix" : "Lyrics"}
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
                      <select
                        value={midiChordMode}
                        onChange={(event) =>
                          setMidiChordMode(event.target.value as "off" | "major" | "minor")
                        }
                        aria-label="MIDI chord mode"
                      >
                        <option value="off">Single note</option>
                        <option value="major">Major chord</option>
                        <option value="minor">Minor chord</option>
                      </select>
                      <select
                        value={midiArpMode}
                        onChange={(event) =>
                          setMidiArpMode(event.target.value as "off" | "up" | "down")
                        }
                        aria-label="MIDI arpeggiator"
                      >
                        <option value="off">Arp off</option>
                        <option value="up">Arp up</option>
                        <option value="down">Arp down</option>
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
                          const note = (selectedLane.midiNotes ?? []).find(
                            (item) =>
                              item.pitch === pitch &&
                              Math.abs(item.time - time) < 0.01
                          );
                          return (
                            <button
                              className={`${note ? "on" : ""}${note && selectedMidiNoteId === note.id ? " selected" : ""}`}
                              key={step}
                              type="button"
                              aria-label={`${midiNoteName(pitch)} at ${time}s`}
                              aria-pressed={Boolean(note)}
                              onClick={() => toggleMidiNote(time, pitch)}
                            />
                          );
                        })}
                      </div>
                    ))}
                  </div>
                  <div className="studio-midi-keyboard" aria-label="Playable MIDI keyboard">
                    {Array.from({ length: 12 }, (_, index) => 60 + index).map((pitch) => {
                      const black = [1, 3, 6, 8, 10].includes(pitch % 12);
                      return (
                        <button
                          key={pitch}
                          type="button"
                          className={black ? "black" : ""}
                          aria-label={`Play ${midiNoteName(pitch)}`}
                          onClick={() => previewMidiPitch(pitch)}
                        >
                          {midiNoteName(pitch)}
                        </button>
                      );
                    })}
                  </div>
                  <div className="studio-midi-connect">
                    <button type="button" onClick={() => void connectMidiInput()}>
                      Connect MIDI
                    </button>
                    <button
                      className={midiRecordArmed ? "on" : ""}
                      type="button"
                      aria-pressed={midiRecordArmed}
                      onClick={() => setMidiRecordArmed((value) => !value)}
                    >
                      {midiRecordArmed ? "Recording MIDI" : "Record MIDI"}
                    </button>
                    <small>
                      {midiStatus ||
                        (midiRecordArmed
                          ? "Play the keyboard or controller to write notes at the playhead."
                          : "Use a connected controller to audition notes.")}
                    </small>
                  </div>
                  {(() => {
                    const note = (selectedLane.midiNotes ?? []).find(
                      (item) => item.id === selectedMidiNoteId
                    );
                    if (!note) return null;
                    return (
                      <div className="studio-midi-note-editor">
                        <div>
                          <b>{midiNoteName(note.pitch)}</b>
                          <span>{note.time.toFixed(1)}s</span>
                        </div>
                        <label>
                          Length
                          <input
                            type="range"
                            min="0.05"
                            max="2"
                            step="0.05"
                            value={note.duration}
                            onChange={(event) =>
                              updateMidiNote(note.id, {
                                duration: Number(event.target.value),
                              })
                            }
                          />
                          <em>{note.duration.toFixed(2)}s</em>
                        </label>
                        <label>
                          Velocity
                          <input
                            type="range"
                            min="0.05"
                            max="1"
                            step="0.05"
                            value={note.velocity}
                            onChange={(event) =>
                              updateMidiNote(note.id, {
                                velocity: Number(event.target.value),
                              })
                            }
                          />
                          <em>{Math.round(note.velocity * 100)}%</em>
                        </label>
                        <button type="button" onClick={() => deleteMidiNote(note.id)}>
                          <Icon name="fa-trash" /> Delete note
                        </button>
                      </div>
                    );
                  })()}
                </div>
              ) : null}
              <div className="studio-lane-colors" aria-label="Track color">
                {COLORS.map((color) => (
                  <button
                    key={color}
                    className={selectedLane.color === color ? "active" : ""}
                    type="button"
                    style={{ background: color }}
                    aria-label={`Set track color ${color}`}
                    onClick={() => updateLane(selectedLane.id, { color })}
                  />
                ))}
              </div>
              {(selectedLane.variant === "ok" || selectedLane.variant === "alt") &&
              !selectedLane.uploadId &&
              !selectedLane.midiNotes ? (
                <div className="studio-take-actions">
                  <div>
                    <span>Take {selectedLane.variant === "alt" ? "B" : "A"}</span>
                    <button
                      type="button"
                      onClick={() => void addAlternateTake(selectedLane)}
                      disabled={takesBusy}
                    >
                      <Icon name={takesBusy ? "fa-spinner" : "fa-clone"} /> Add alternate take
                    </button>
                  </div>
                  {takesError ? (
                    <small className="studio-stem-error">{takesError}</small>
                  ) : (
                    <small>Adds the other Suno take as a parallel lane for comping.</small>
                  )}
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
              <div className="studio-fade-shapes">
                <label>Fade in
                  <select
                    value={selectedLane.fadeInCurve ?? "linear"}
                    onChange={(event) =>
                      updateLane(selectedLane.id, {
                        fadeInCurve: event.target.value as Clip["fadeInCurve"],
                      })
                    }
                  >
                    <option value="linear">Linear</option>
                    <option value="exponential">Exponential</option>
                  </select>
                </label>
                <label>Fade out
                  <select
                    value={selectedLane.fadeOutCurve ?? "linear"}
                    onChange={(event) =>
                      updateLane(selectedLane.id, {
                        fadeOutCurve: event.target.value as Clip["fadeOutCurve"],
                      })
                    }
                  >
                    <option value="linear">Linear</option>
                    <option value="exponential">Exponential</option>
                  </select>
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
              <div className="studio-eq studio-presets">
                <div className="studio-eq-head">
                  <span>Plugin presets</span>
                  <small>Selected track</small>
                </div>
                <div className="studio-preset-grid">
                  {MIX_PRESETS.map((preset) => (
                    <button
                      key={preset.id}
                      type="button"
                      onClick={() => updateLane(selectedLane.id, preset.patch)}
                    >
                      {preset.name}
                    </button>
                  ))}
                </div>
              </div>
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
                        <input
                          type="range"
                          min="0"
                          max="100"
                          step="1"
                          value={point.value}
                          aria-label={`Volume at ${point.time.toFixed(1)} seconds`}
                          onChange={(event) =>
                            updateVolumeAutomationPoint(point.id, {
                              value: Number(event.target.value),
                            })
                          }
                        />
                        <b>{Math.round(point.value)}%</b>
                        <select
                          value={point.curve ?? "linear"}
                          aria-label={`Curve at ${point.time.toFixed(1)} seconds`}
                          onChange={(event) =>
                            updateVolumeAutomationPoint(point.id, {
                              curve: event.target.value as AutomationPoint["curve"],
                            })
                          }
                        >
                          <option value="linear">Lin</option>
                          <option value="exponential">Exp</option>
                        </select>
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
                  <span>Filter</span>
                  <button
                    type="button"
                    onClick={() =>
                      updateLane(selectedLane.id, {
                        filterCutoff: 20000,
                        filterResonance: 0.7,
                      })
                    }
                  >
                    Reset
                  </button>
                </div>
                <label>Cutoff <b>{Math.round((selectedLane.filterCutoff ?? 20000) / 100) / 10} kHz</b>
                  <input
                    type="range"
                    min="100"
                    max="20000"
                    step="100"
                    value={selectedLane.filterCutoff ?? 20000}
                    onChange={(event) =>
                      updateLane(selectedLane.id, { filterCutoff: Number(event.target.value) })
                    }
                  />
                </label>
                <label>Resonance <b>{(selectedLane.filterResonance ?? 0.7).toFixed(1)}</b>
                  <input
                    type="range"
                    min="0.1"
                    max="12"
                    step="0.1"
                    value={selectedLane.filterResonance ?? 0.7}
                    onChange={(event) =>
                      updateLane(selectedLane.id, { filterResonance: Number(event.target.value) })
                    }
                  />
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
              {activeInspectorTab === "lyrics" ? (
                <div className="studio-lyrics">
                  <div className="studio-eq-head">
                    <span>Lyrics</span>
                    <button
                      type="button"
                      onClick={() => void loadLyrics(true)}
                      disabled={lyricsLoading}
                    >
                      {lyricsLoading ? "Loading…" : "Refresh"}
                    </button>
                  </div>
                  {lyricsError ? (
                    <small className="studio-stem-error">{lyricsError}</small>
                  ) : null}
                  {!lyricsLoading && !lyricsError && lyricLines.length ? (
                    <div className="studio-lyric-lines">
                      {lyricLines.map((line, index) => (
                        <button
                          type="button"
                          className="studio-lyric-line"
                          key={`${index}-${line.start}`}
                          onClick={() =>
                            seekTo(
                              selectedLane.start +
                                Math.max(0, line.start - selectedLane.offset)
                            )
                          }
                        >
                          <span>{formatTime(line.start)}</span>
                          <p>{line.text}</p>
                        </button>
                      ))}
                    </div>
                  ) : null}
                  {!lyricsLoading && !lyricsError && !lyricLines.length ? (
                    <small>No lyrics were found for this clip.</small>
                  ) : null}
                </div>
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
              <div className="studio-personas">
                <div className="studio-persona-head">
                  <span>Personas</span>
                  <button type="button" onClick={() => void refreshPersonas()} disabled={personasBusy}>
                    {personasBusy ? "Loading…" : "Refresh"}
                  </button>
                </div>
                <select
                  value={selectedPersonaId}
                  onChange={(event) => setSelectedPersonaId(event.target.value)}
                  disabled={personasBusy}
                  aria-label="Studio persona"
                >
                  <option value="">No persona</option>
                  {personas
                    .filter((persona) => persona.status === "complete" && persona.provider_persona_id)
                    .map((persona) => (
                      <option key={persona.id} value={persona.provider_persona_id ?? ""}>
                        {persona.name}
                      </option>
                    ))}
                </select>
                <div className="studio-persona-create">
                  <input
                    value={personaName}
                    onChange={(event) => setPersonaName(event.target.value)}
                    placeholder="New persona name"
                    maxLength={80}
                  />
                  <button
                    type="button"
                    onClick={() => void createPersonaFromSelected()}
                    disabled={
                      personasBusy ||
                      !selectedLane ||
                      (selectedLane.variant !== "ok" && selectedLane.variant !== "alt")
                    }
                  >
                    Create
                  </button>
                </div>
                {personasStatus ? <small>{personasStatus}</small> : null}
                {personasError ? <small className="studio-stem-error">{personasError}</small> : null}
                <small>Personas apply when you replace a section.</small>
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
                  <button
                    type="button"
                    onClick={() =>
                      void runStudioEdit("Remaster", () =>
                        requestStudioRemaster({
                          taskId: selectedLane.generationId,
                          variant: selectedLane.variant,
                          projectId,
                        })
                      )
                    }
                    disabled={editBusy || stemsBusy || (selectedLane.variant !== "ok" && selectedLane.variant !== "alt")}
                  >
                    <Icon name="fa-wand-sparkles" /> Remaster
                  </button>
                  <button
                    type="button"
                    onClick={openMashup}
                    disabled={editBusy || stemsBusy || lanes.filter((lane) => lane.variant === "ok" || lane.variant === "alt").length < 2}
                  >
                    <Icon name="fa-object-group" /> Mashup
                  </button>
                  <button
                    type="button"
                    onClick={() => void runCoverImage()}
                    disabled={editBusy || stemsBusy || !editPrompt.trim() || (selectedLane.variant !== "ok" && selectedLane.variant !== "alt")}
                  >
                    <Icon name="fa-image" /> Cover art
                  </button>
                </div>
                {selectedLane.uploadId ? (
                  <div className="studio-upload-edit-actions">
                    <span>Uploaded audio</span>
                    <button
                      type="button"
                      onClick={() => {
                        const uploadId = selectedLane.uploadId;
                        if (!uploadId) return;
                        void runStudioEdit(
                          "Upload extend",
                          () =>
                            requestStudioUploadExtend({
                              uploadId,
                              prompt: editPrompt.trim(),
                              continueAt: selectedLane.offset + selectedLane.duration,
                              title: selectedLane.title,
                              tags: selectedLane.style,
                              projectId,
                            }),
                          selectedLane,
                          true
                        );
                      }}
                      disabled={editBusy || stemsBusy}
                    >
                      <Icon name="fa-arrow-right-long" /> Extend upload
                    </button>
                    <button
                      type="button"
                      onClick={() => {
                        const uploadId = selectedLane.uploadId;
                        if (!uploadId) return;
                        void runStudioEdit(
                          "Upload cover",
                          () =>
                            requestStudioUploadCover({
                              uploadId,
                              prompt: editPrompt.trim(),
                              coverStartS: selectedLane.offset,
                              coverEndS: selectedLane.offset + selectedLane.duration,
                              title: selectedLane.title,
                              tags: selectedLane.style,
                              projectId,
                            }),
                          selectedLane,
                          true
                        );
                      }}
                      disabled={editBusy || stemsBusy}
                    >
                      <Icon name="fa-compact-disc" /> Cover upload
                    </button>
                  </div>
                ) : null}
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
                        personaId: selectedPersonaId || undefined,
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
          <span className="studio-master-comp" title="Master bus compression">
            <Icon name="fa-compress" />
            <input type="range" min="0" max="100" value={masterCompressor} onChange={(event) => setMasterCompressor(Number(event.target.value))} aria-label="Master compression" />
            <b>{masterCompressor}%</b>
          </span>
          <span className="studio-master-meter" aria-label="Master output level">
            <i style={{ transform: `scaleY(${Math.max(0.04, masterMeter)})` }} />
            <i style={{ transform: `scaleY(${Math.max(0.04, masterMeter)})` }} />
          </span>
          <button
            className={`studio-master-eq-btn${masterEqOpen ? " on" : ""}`}
            type="button"
            onClick={() => setMasterEqOpen((value) => !value)}
            aria-expanded={masterEqOpen}
            title="Master bus EQ"
          >
            <Icon name="fa-sliders" /> EQ
          </button>
          {masterEqOpen ? (
            <div className="studio-master-eq-popover">
              <span>Master bus</span>
              <div className="studio-master-presets">
                {MASTER_PRESETS.map((preset) => (
                  <button
                    key={preset.id}
                    type="button"
                    onClick={() => applyMasterPreset(preset.patch)}
                  >
                    {preset.name}
                  </button>
                ))}
              </div>
              <label>
                Drive
                <input type="range" min="0" max="100" step="1" value={masterDrive} onChange={(event) => setMasterDrive(Number(event.target.value))} />
                <b>{masterDrive}%</b>
              </label>
              {([
                ["Low", masterLow, setMasterLow],
                ["Mid", masterMid, setMasterMid],
                ["High", masterHigh, setMasterHigh],
              ] as const).map(([label, value, setter]) => (
                <label key={label}>
                  {label}
                  <input
                    type="range"
                    min="-12"
                    max="12"
                    step="0.5"
                    value={value}
                    onChange={(event) => setter(Number(event.target.value))}
                  />
                  <b>{value > 0 ? "+" : ""}{value} dB</b>
                </label>
              ))}
              <button
                type="button"
                onClick={() => {
                  setMasterDrive(0);
                  setMasterLow(0);
                  setMasterMid(0);
                  setMasterHigh(0);
                }}
              >
                Reset EQ
              </button>
            </div>
          ) : null}
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
            <div className="studio-project-search-row">
              <input
                className="studio-project-search"
                value={projectSearch}
                onChange={(event) => setProjectSearch(event.target.value)}
                placeholder="Search projects…"
                aria-label="Search projects"
              />
              <select
                value={projectSort}
                onChange={(event) =>
                  setProjectSort(event.target.value as "updated" | "title")
                }
                aria-label="Sort projects"
              >
                <option value="updated">Last updated</option>
                <option value="title">Name</option>
              </select>
            </div>
            <div className="studio-versions-list">
              {projectsBusy && !projectList.length ? <p>Loading projects…</p> : null}
              {!projectsBusy && !projectList.length ? <p>No saved projects yet.</p> : null}
              {!projectsBusy && projectList.length && !filteredProjects.length ? (
                <p>No projects match your search.</p>
              ) : null}
              {filteredProjects.map((project) => (
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
                      type="button"
                      onClick={() => void duplicateProject(project)}
                      disabled={projectsBusy}
                    >
                      Duplicate
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
      {mashupOpen ? (
        <div className="studio-modal-backdrop" role="dialog" aria-modal="true" aria-label="Mashup">
          <div className="studio-versions-modal">
            <div className="studio-versions-head">
              <div>
                <h2>Mashup</h2>
                <p>Select two original generated tracks.</p>
              </div>
              <button type="button" aria-label="Close mashup" onClick={() => setMashupOpen(false)}>
                <Icon name="fa-xmark" />
              </button>
            </div>
            <div className="studio-mashup-list">
              {lanes.filter((lane) => lane.variant === "ok" || lane.variant === "alt").map((lane) => (
                <label key={lane.id} className="studio-mashup-row">
                  <input
                    type="checkbox"
                    checked={mashupSelection.includes(lane.id)}
                    onChange={() => toggleMashupLane(lane.id)}
                  />
                  <span style={{ background: lane.color }} />
                  <b>{lane.title}</b>
                  <small>{lane.style}</small>
                </label>
              ))}
            </div>
            <textarea
              className="studio-mashup-prompt"
              value={mashupPrompt}
              onChange={(event) => setMashupPrompt(event.target.value)}
              placeholder="Optional mashup direction…"
              rows={2}
            />
            {mashupError ? <small className="studio-stem-error">{mashupError}</small> : null}
            <button
              className="btn btn-primary"
              type="button"
              onClick={() => void createMashup()}
              disabled={mashupSelection.length !== 2 || editBusy}
            >
              <Icon name="fa-object-group" /> Create mashup
            </button>
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
                <div className="studio-share-link-actions">
                  <a className="studio-share-open" href={shareUrl} target="_blank" rel="noreferrer">
                    Open preview <Icon name="fa-arrow-up-right-from-square" />
                  </a>
                  <button className="studio-share-revoke" type="button" onClick={() => void revokeShare()}>
                    Revoke link
                  </button>
                </div>
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
                <label className="studio-share-permission">
                  Expires
                  <select
                    value={shareDays}
                    onChange={(event) => setShareDays(Number(event.target.value))}
                    disabled={shareBusy}
                  >
                    <option value={1}>1 day</option>
                    <option value={7}>7 days</option>
                    <option value={30}>30 days</option>
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
                <div
                  className={`studio-project-comment${comment.parent_id ? " reply" : ""}`}
                  key={comment.id}
                >
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
        const laneIndex = lanes.findIndex((item) => item.id === lane.id);
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
            <button
              type="button"
              disabled={laneIndex <= 0}
              onClick={() => { setClipMenu(null); moveLane(lane, -1); }}
            >
              <Icon name="fa-arrow-up" /> Move track up
            </button>
            <button
              type="button"
              disabled={laneIndex >= lanes.length - 1}
              onClick={() => { setClipMenu(null); moveLane(lane, 1); }}
            >
              <Icon name="fa-arrow-down" /> Move track down
            </button>
            <button type="button" onClick={() => { setClipMenu(null); splitLane(lane, playhead); }}>
              <Icon name="fa-scissors" /> Split at playhead
            </button>
            <button type="button" onClick={() => { setClipMenu(null); duplicateLane(lane); }}>
              <Icon name="fa-copy" /> Duplicate
            </button>
            <button type="button" onClick={() => { setClipMenu(null); updateLane(lane.id, { muted: !lane.muted }); }}>
              <Icon name={lane.muted ? "fa-volume-high" : "fa-volume-xmark"} /> {lane.muted ? "Unmute" : "Mute"}
            </button>
            <button type="button" onClick={() => { setClipMenu(null); copyMixSettings(lane); }}>
              <Icon name="fa-clipboard" /> Copy mix settings
            </button>
            <button type="button" onClick={() => { setClipMenu(null); pasteMixSettings(lane); }} disabled={!mixClipboard}>
              <Icon name="fa-paste" /> Paste mix settings
            </button>
            <button type="button" onClick={() => { setClipMenu(null); resetMixSettings(lane); }}>
              <Icon name="fa-rotate-left" /> Reset mix
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
