/**
 * Export (roadmap W4.3).
 *
 * The reference's export is a three-item menu that fires and forgets: no dialog, no
 * progress, and an unnamed project is saved first (spec §87). We keep the same
 * shape — pick a scope, get a file — but render locally so there is no round trip.
 *
 * Everything here is context-injected and free of React, so it can be exercised
 * directly with an OfflineAudioContext (see the dev handle below).
 */

import {
  schedulePanAutomation,
  scheduleVolumeAutomation,
  type AutomationPoint,
} from "@/lib/studio-automation";
import { buildMasterBus, type MasterChainEntry } from "@/lib/studio-master-bus";
import {
  clipRate,
  dbToGain,
  planClipPlayback,
  reverseBuffer,
  sanitizeClipAudio,
  type ClipAudioSettings,
} from "@/lib/studio-clip-audio";
import { normaliseChannels } from "@/lib/studio-normalise";
import { buildPluginChain } from "@/lib/studio-plugin-audio";
import {
  normalizeMidiInstrument,
  sanitizePoints,
  scheduleMidiNote,
  valueAt,
  type MidiInstrument,
  type MidiNote,
} from "@/lib/studio-midi";
import type { PluginChainEntry } from "@/lib/studio-plugins";

export type ExportClip = {
  id: string;
  start?: number;
  duration?: number;
  /** Seconds into the source file where the clip begins (left trim). */
  offset?: number;
  /** Fade-in length in seconds (S25). */
  fadeIn?: number;
  /** Fade-out length in seconds (S25). */
  fadeOut?: number;
  /** Clip Settings: volume, loop, reverse, pitch, speed (S30/§81). */
  audio?: Partial<ClipAudioSettings>;
  audioUrl?: string | null;
  midi?: {
    notes?: MidiNote[];
    bend?: { at: number; value: number }[];
    mod?: { at: number; value: number }[];
  };
  /** MIDI synth voice (S31); triangle when absent. */
  instrument?: MidiInstrument;
};

export type ExportTrack = {
  id: string;
  name?: string;
  volume?: number;
  pan?: number;
  muted?: boolean;
  solo?: boolean;
  /** Volume automation points in absolute timeline seconds. */
  volumeAutomation?: AutomationPoint[];
  /** Pan automation points (-100..100) in absolute timeline seconds. */
  panAutomation?: AutomationPoint[];
  clipIds: string[];
};

/** 16-bit PCM WAV from a set of rendered channels. */
export function encodeWav(channels: Float32Array[], sampleRate: number): Uint8Array {
  const channelCount = Math.max(1, channels.length);
  const frames = channels[0]?.length ?? 0;
  const bytesPerFrame = channelCount * 2;
  const dataSize = frames * bytesPerFrame;
  const buffer = new ArrayBuffer(44 + dataSize);
  const view = new DataView(buffer);

  const writeString = (offset: number, value: string) => {
    for (let i = 0; i < value.length; i++) view.setUint8(offset + i, value.charCodeAt(i));
  };

  writeString(0, "RIFF");
  view.setUint32(4, 36 + dataSize, true);
  writeString(8, "WAVE");
  writeString(12, "fmt ");
  view.setUint32(16, 16, true); // PCM chunk size
  view.setUint16(20, 1, true); // format = PCM
  view.setUint16(22, channelCount, true);
  view.setUint32(24, sampleRate, true);
  view.setUint32(28, sampleRate * bytesPerFrame, true);
  view.setUint16(32, bytesPerFrame, true);
  view.setUint16(34, 16, true);
  writeString(36, "data");
  view.setUint32(40, dataSize, true);

  let offset = 44;
  for (let frame = 0; frame < frames; frame++) {
    for (let channel = 0; channel < channelCount; channel++) {
      const sample = Math.max(-1, Math.min(1, channels[channel][frame] ?? 0));
      view.setInt16(offset, sample < 0 ? sample * 0x8000 : sample * 0x7fff, true);
      offset += 2;
    }
  }
  return new Uint8Array(buffer);
}

export type RenderOptions = {
  sampleRate?: number;
  /** Which clips to include; omit for the whole project. */
  clipIds?: Set<string>;
  /** Restrict to a time window (seconds). */
  from?: number;
  to?: number;
  chain?: MasterChainEntry[];
  /** Per-track plugin chains, keyed by track id (applied before the track gain). */
  chains?: Record<string, PluginChainEntry[]>;
  /**
   * Mix/range renders follow the solo state (like playback); per-track exports must not,
   * or bouncing a non-soloed track would produce silence.
   */
  honourSolo?: boolean;
  /** Master level multiplier (0–1); defaults to the historical 0.85. */
  masterGain?: number;
  /**
   * Normalise the finished render to this sample-peak target (dBFS). Off when
   * omitted, so a plain render stays byte-identical to what the mix produced.
   */
  normalise?: number | null;
};

/**
 * Render a mix to WAV bytes. `buffers` are decoded per clip id, so callers can render
 * the full mix and single tracks from the same decode pass.
 */
export async function renderMix(
  bufferMap: Map<string, AudioBuffer>,
  clips: ExportClip[],
  tracks: ExportTrack[],
  options: RenderOptions = {}
): Promise<Uint8Array> {
  const sampleRate = options.sampleRate ?? 44100;
  const from = Math.max(0, options.from ?? 0);
  const lastEnd = clips.reduce(
    (max, clip) => Math.max(max, (clip.start ?? 0) + (clip.duration ?? 0)),
    0
  );
  const to = Math.max(from + 0.1, options.to ?? lastEnd);
  const seconds = to - from;

  const context = new OfflineAudioContext(2, Math.ceil(seconds * sampleRate), sampleRate);
  const master = context.createGain();
  master.gain.value = Math.max(0, Math.min(1, options.masterGain ?? 0.85));
  const bus = buildMasterBus(context, options.chain ?? []);
  master.connect(bus.input);
  bus.output.connect(context.destination);

  // One gain + optional plugin chain per track, shared by that track's clips so an
  // effect is heard once rather than duplicated per clip.
  const trackNodes = new Map<string, AudioNode>();
  const trackGains = new Map<string, GainNode>();
  const trackPans = new Map<string, StereoPannerNode>();
  const anySolo = tracks.some((track) => track.solo);
  function trackInput(trackId: string, volume: number, pan = 0): AudioNode {
    const existing = trackNodes.get(trackId);
    if (existing) return existing;
    const gain = context.createGain();
    gain.gain.value = Math.max(0, volume) / 100;
    const panner = context.createStereoPanner();
    panner.pan.value = Math.max(-1, Math.min(1, pan / 100));
    trackGains.set(trackId, gain);
    trackPans.set(trackId, panner);
    gain.connect(panner);
    panner.connect(master);
    const entries = options.chains?.[trackId] ?? [];
    if (entries.length > 0) {
      const chain = buildPluginChain(context, entries);
      chain.output.connect(gain);
      trackNodes.set(trackId, chain.input);
      return chain.input;
    }
    trackNodes.set(trackId, gain);
    return gain;
  }

  for (const track of tracks) {
    const hasVolume = Boolean(track.volumeAutomation?.length);
    const hasPan = Boolean(track.panAutomation?.length);
    if (!hasVolume && !hasPan) continue;
    const audible = !track.muted && (!anySolo || track.solo);
    trackInput(track.id, audible ? track.volume ?? 80 : 0, track.pan ?? 0);
    if (!audible) continue;
    const gain = trackGains.get(track.id);
    const panner = trackPans.get(track.id);
    if (gain && hasVolume) {
      scheduleVolumeAutomation(gain.gain, track.volumeAutomation!, {
        from,
        when: 0,
        rate: 1,
        fallback: track.volume ?? 80,
      });
    }
    if (panner && hasPan) {
      schedulePanAutomation(panner.pan, track.panAutomation!, {
        from,
        when: 0,
        rate: 1,
        fallback: track.pan ?? 0,
      });
    }
  }

  for (const clip of clips) {
    if (options.clipIds && !options.clipIds.has(clip.id)) continue;
    const buffer = bufferMap.get(clip.id);
    if (!buffer) continue;
    const start = clip.start ?? 0;
    const duration = clip.duration ?? buffer.duration;
    if (start + duration <= from || start >= to) continue;
    const track = tracks.find((item) => item.clipIds.includes(clip.id));
    if (track?.muted) continue;
    // Bounce what you hear: a soloed track silences the others, exactly like playback.
    if (options.honourSolo !== false && track && anySolo && !track.solo) continue;

    const when = Math.max(0, start - from);
    const offset = Math.max(0, from - start);
    const playable = Math.min(duration - offset, to - Math.max(start, from));
    if (playable <= 0) continue;

    const source = context.createBufferSource();
    const settings = sanitizeClipAudio(clip.audio);
    const rate = clipRate(settings);
    const plan = planClipPlayback({
      bufferDuration: buffer.duration,
      clipDuration: duration,
      intoClip: offset,
      offset: Math.max(0, clip.offset ?? 0),
      rate,
      reverse: settings.reverse,
      loop: settings.loop,
    });
    source.buffer = settings.reverse ? reverseBuffer(context, buffer) : buffer;
    // The export tests drive a minimal AudioContext stub; a real one always has this.
    if (source.playbackRate) source.playbackRate.value = rate;
    if (plan.loop) {
      source.loop = true;
      source.loopStart = plan.loopStart;
      source.loopEnd = plan.loopEnd;
    }
    const trackInputNode = trackInput(
      track?.id ?? clip.id,
      track?.volume ?? 80,
      track?.pan ?? 0
    );
    const fadeIn = Math.min(clip.fadeIn ?? 0, duration);
    const fadeOut = Math.min(clip.fadeOut ?? 0, duration);
    // Volume is a separate node so the fade automation stays a clean 0→1 ramp.
    let nodeInput: AudioNode = trackInputNode;
    if (settings.gainDb !== 0) {
      const volume = context.createGain();
      volume.gain.value = dbToGain(settings.gainDb);
      volume.connect(trackInputNode);
      nodeInput = volume;
    }
    if (fadeIn > 0 || fadeOut > 0) {
      const clipGain = context.createGain();
      const intoClip = Math.max(0, from - start);
      const initial = fadeIn > 0 ? (intoClip >= fadeIn ? 1 : intoClip / fadeIn) : 1;
      clipGain.gain.setValueAtTime(initial, when);
      if (fadeIn > 0 && intoClip < fadeIn) {
        clipGain.gain.linearRampToValueAtTime(1, when + (fadeIn - intoClip));
      }
      if (fadeOut > 0 && playable > 0) {
        const fadeStart = Math.max(0, playable - fadeOut);
        clipGain.gain.setValueAtTime(1, when + fadeStart);
        clipGain.gain.linearRampToValueAtTime(0, when + playable);
      }
      clipGain.connect(nodeInput);
      source.connect(clipGain);
    } else {
      source.connect(nodeInput);
    }
    const node = source as AudioBufferSourceNode & { start: (w: number, o?: number, d?: number) => void };
    if (plan.loop) {
      node.start(when, plan.bufferStart);
      // A looped clip still ends with its timeline length.
      source.stop(when + Math.max(0.05, playable));
    } else {
      node.start(when, plan.bufferStart, Math.max(0.001, plan.bufferLength ?? playable));
    }
  }

  // MIDI clips render through the same track inputs, so chains/mix apply to them too.
  for (const clip of clips) {
    if (options.clipIds && !options.clipIds.has(clip.id)) continue;
    const notes = clip.midi?.notes ?? [];
    if (notes.length === 0) continue;
    const track = tracks.find((item) => item.clipIds.includes(clip.id));
    const audible = track ? !track.muted && (!anySolo || track.solo) : true;
    if (!audible) continue;
    const destination = trackInput(
      track?.id ?? clip.id,
      track?.volume ?? 80,
      track?.pan ?? 0
    );
    const bend = sanitizePoints(clip.midi?.bend, -1, 1);
    const mod = sanitizePoints(clip.midi?.mod, 0, 1);
    for (const note of notes) {
      const absolute = (clip.start ?? 0) + note.start;
      if (absolute < from - 0.001 || absolute >= to) continue;
      scheduleMidiNote(
        context,
        destination,
        note,
        Math.max(0, absolute - from),
        1,
        {
          bend: valueAt(bend, note.start, 0),
          mod: valueAt(mod, note.start, 0),
        },
        normalizeMidiInstrument(clip.instrument),
      );
    }
  }

  const rendered = await context.startRendering();
  const raw = Array.from({ length: rendered.numberOfChannels }, (_, index) =>
    rendered.getChannelData(index)
  );
  const channels =
    options.normalise == null ? raw : normaliseChannels(raw, options.normalise).channels;
  return encodeWav(channels, sampleRate);
}

// Dev-only handle so the exporter can be measured without wiring a download.
if (typeof window !== "undefined" && process.env.NODE_ENV !== "production") {
  (window as unknown as { __studioExport?: { renderMix: typeof renderMix; encodeWav: typeof encodeWav } })
    .__studioExport = { renderMix, encodeWav };
}
