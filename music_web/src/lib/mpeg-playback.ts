/** Protected MPEG playback. Never create a downloadable audio/mpeg blob or data URL. */

import type { HoldSeekResult } from '@/lib/crios-now-playing-debug';
import { stripToMpegSync } from '@/lib/mpeg-sync';

let sharedAudioContext: AudioContext | null = null;
let keepAliveSource: AudioBufferSourceNode | null = null;
let keepAliveGain: GainNode | null = null;
let detachedHold: HTMLAudioElement | null = null;
let silentWavUri: string | null = null;
let audioWatchInstalled = false;

type MediaSourceLike = {
  isTypeSupported?: (mime: string) => boolean;
};

export function isSafariMpegMseBroken(): boolean {
  if (typeof navigator === 'undefined') return false;
  const ua = navigator.userAgent || '';
  if (/iPhone|iPad|iPod/i.test(ua)) return true;
  if (navigator.platform === 'MacIntel' && (navigator.maxTouchPoints || 0) > 1) return true;
  if (/CriOS|FxiOS|EdgiOS/i.test(ua)) return true;
  const vendor = navigator.vendor || '';
  return /Apple/i.test(vendor) && /Safari/i.test(ua) && !/Chrome|Chromium|Android/i.test(ua);
}

/** iOS Chrome (CriOS) — same WebKit engine but stricter autoplay after async session work. */
export function isIosChrome(): boolean {
  if (typeof navigator === 'undefined') return false;
  return /CriOS/i.test(navigator.userAgent || '');
}

/** Web Audio + silent hold on iOS Chrome only (Safari uses HLS — do not branch on this for Safari). */
export function isIosChromeWebAudio(): boolean {
  return isIosChrome() && isSafariMpegMseBroken();
}

export function canUseMpegMediaSource(): boolean {
  if (typeof window === 'undefined') return false;
  try {
    if (typeof MediaSource !== 'undefined' && MediaSource?.isTypeSupported?.('audio/mpeg')) {
      return MediaSource.isTypeSupported('audio/mpeg') === true;
    }
    const managed = (window as Window & { ManagedMediaSource?: MediaSourceLike }).ManagedMediaSource;
    if (managed?.isTypeSupported) {
      return managed.isTypeSupported('audio/mpeg') === true;
    }
  } catch {
    return false;
  }
  return false;
}

export function shouldUseMpegMediaSource(): boolean {
  return canUseMpegMediaSource() && !isSafariMpegMseBroken();
}

/** iOS Safari: AES-128 HLS via native HTML audio (lock screen / Dynamic Island). */
export function shouldUseHlsPlayback(): boolean {
  return isSafariMpegMseBroken() && !isIosChrome();
}

/** iOS Safari fallback when HLS is not packaged yet. */
export function shouldUseNativeHtmlPlayback(): boolean {
  return shouldUseHlsPlayback();
}

/** iOS Safari: in-DOM <video> for HLS — lock screen binds to video better than audio. */
export function shouldUseIosNativeVideoElement(): boolean {
  return shouldUseHlsPlayback() || isIosChrome();
}

/** HLS native lane: Safari iOS, or iOS Chrome (same WebKit HLS — not Web Audio silent hold). */
export function shouldUseIosHlsPlayback(): boolean {
  return shouldUseHlsPlayback() || isIosChrome();
}

/** Prime in-DOM <video> during the user tap — CriOS loses gesture after session fetch. Safari HLS does not use this. */
export function primeIosChromeVideoGesture(video: HTMLVideoElement) {
  if (!isIosChrome()) return;
  prepareHtmlVideo(video);
  video.loop = true;
  video.muted = false;
  video.volume = 0.0001;
  const src = (video.currentSrc || video.getAttribute('src') || '').trim();
  if (!src.includes('camxora-silent-hold.wav')) {
    video.src = '/camxora-silent-hold.wav';
  }
  void video.play().catch(() => undefined);
}

/** Wait until licensed stream is buffered on a media element. */
export function waitForNativePlayReady(media: HTMLMediaElement, timeoutMs = 20000): Promise<void> {
  return new Promise((resolve, reject) => {
    if (media.readyState >= HTMLMediaElement.HAVE_FUTURE_DATA) {
      resolve();
      return;
    }
    const timeout = window.setTimeout(() => {
      cleanup();
      reject(new Error('Native play timeout'));
    }, timeoutMs);
    const onReady = () => {
      cleanup();
      resolve();
    };
    const onError = () => {
      cleanup();
      reject(new Error('Native media load failed'));
    };
    const cleanup = () => {
      window.clearTimeout(timeout);
      media.removeEventListener('canplay', onReady);
      media.removeEventListener('canplaythrough', onReady);
      media.removeEventListener('error', onError);
    };
    media.addEventListener('canplay', onReady, { once: true });
    media.addEventListener('canplaythrough', onReady, { once: true });
    media.addEventListener('error', onError, { once: true });
  });
}

/** Resolve when output actually starts (iOS Now Playing hooks this better than canplay). */
export function waitForNativePlaybackStart(media: HTMLMediaElement, timeoutMs = 20000): Promise<void> {
  return new Promise((resolve, reject) => {
    if (!media.paused && media.readyState >= HTMLMediaElement.HAVE_CURRENT_DATA) {
      resolve();
      return;
    }
    const timeout = window.setTimeout(() => {
      cleanup();
      reject(new Error('Native playback start timeout'));
    }, timeoutMs);
    const onPlaying = () => {
      cleanup();
      resolve();
    };
    const onError = () => {
      cleanup();
      reject(new Error('Native media playback failed'));
    };
    const cleanup = () => {
      window.clearTimeout(timeout);
      media.removeEventListener('playing', onPlaying);
      media.removeEventListener('error', onError);
    };
    media.addEventListener('playing', onPlaying, { once: true });
    media.addEventListener('error', onError, { once: true });
  });
}

/** Attach playing listener, then play() — required order for iOS Now Playing. */
export function startNativePlayback(media: HTMLMediaElement, timeoutMs = 20000): Promise<void> {
  return new Promise((resolve, reject) => {
    if (!media.paused && media.readyState >= HTMLMediaElement.HAVE_CURRENT_DATA) {
      resolve();
      return;
    }
    const timeout = window.setTimeout(() => {
      cleanup();
      reject(new Error('Native playback start timeout'));
    }, timeoutMs);
    const onPlaying = () => {
      cleanup();
      resolve();
    };
    const onError = () => {
      cleanup();
      reject(new Error('Native media playback failed'));
    };
    const cleanup = () => {
      window.clearTimeout(timeout);
      media.removeEventListener('playing', onPlaying);
      media.removeEventListener('error', onError);
    };
    media.addEventListener('playing', onPlaying, { once: true });
    media.addEventListener('error', onError, { once: true });
    void media.play().catch((err) => {
      cleanup();
      reject(err);
    });
  });
}

export function isLicensedStreamSrc(src: string | null | undefined): boolean {
  const text = String(src || '').trim();
  if (!text) return false;
  return /\/licenses\/hls\//.test(text) || /\/licenses\/play\//.test(text);
}

export function clearPlayerForNativeStream(media: HTMLMediaElement) {
  media.pause();
  media.loop = false;
  media.removeAttribute('src');
  try {
    media.load();
  } catch {
    /* Safari may reject load on detached element */
  }
}

export function prepareHtmlVideo(video: HTMLVideoElement) {
  video.playsInline = true;
  video.setAttribute('playsinline', 'true');
  video.setAttribute('webkit-playsinline', 'true');
  video.preload = 'auto';
  video.removeAttribute('crossorigin');
  video.setAttribute('x-webkit-airplay', 'allow');
}

export function createMpegMediaSource(): MediaSource {
  const w = window as Window & { ManagedMediaSource?: typeof MediaSource };
  if (typeof MediaSource !== 'undefined' && MediaSource?.isTypeSupported?.('audio/mpeg')) {
    return new MediaSource();
  }
  if (w.ManagedMediaSource?.isTypeSupported?.('audio/mpeg')) {
    return new w.ManagedMediaSource();
  }
  throw new Error('MPEG MediaSource is not available.');
}

export function getSharedAudioContext(): AudioContext {
  const AC =
    window.AudioContext ||
    (window as unknown as { webkitAudioContext?: typeof AudioContext }).webkitAudioContext;
  if (!AC) throw new Error('Web Audio is not available on this device.');
  if (!sharedAudioContext || sharedAudioContext.state === 'closed') {
    sharedAudioContext = new AC();
    keepAliveSource = null;
    keepAliveGain = null;
  }
  return sharedAudioContext;
}

function buildSilentWavBytes(durationSeconds: number): Uint8Array {
  const sampleRate = 8000;
  const samples = Math.max(1, Math.floor(sampleRate * durationSeconds));
  const buffer = new ArrayBuffer(44 + samples);
  const view = new DataView(buffer);
  const writeStr = (offset: number, text: string) => {
    for (let i = 0; i < text.length; i += 1) {
      view.setUint8(offset + i, text.charCodeAt(i));
    }
  };
  writeStr(0, 'RIFF');
  view.setUint32(4, 36 + samples, true);
  writeStr(8, 'WAVE');
  writeStr(12, 'fmt ');
  view.setUint32(16, 16, true);
  view.setUint16(20, 1, true);
  view.setUint16(22, 1, true);
  view.setUint32(24, sampleRate, true);
  view.setUint32(28, sampleRate, true);
  view.setUint16(32, 1, true);
  view.setUint16(34, 8, true);
  writeStr(36, 'data');
  view.setUint32(40, samples, true);
  for (let i = 0; i < samples; i += 1) {
    view.setUint8(44 + i, 128);
  }
  return new Uint8Array(buffer);
}

function buildSilentWavDataUri(durationSeconds: number): string {
  let binary = '';
  const bytes = buildSilentWavBytes(durationSeconds);
  for (let i = 0; i < bytes.length; i += 1) {
    binary += String.fromCharCode(bytes[i]);
  }
  return `data:audio/wav;base64,${btoa(binary)}`;
}

function silentWavDataUri(): string {
  if (silentWavUri) return silentWavUri;
  silentWavUri = buildSilentWavDataUri(0.2);
  return silentWavUri;
}

const PLAYER_SILENT_HOLD_SRC = '/camxora-silent-hold.wav';

export function isPlayerSilentHoldAudio(audio: HTMLAudioElement | null | undefined): boolean {
  if (!audio) return false;
  const src = (audio.currentSrc || audio.getAttribute('src') || audio.src || '').trim();
  return src.includes('camxora-silent-hold.wav');
}

function holdAudioContext(ctx: AudioContext) {
  if (keepAliveSource) return;
  const frames = Math.max(1, Math.floor(ctx.sampleRate / 10));
  const buffer = ctx.createBuffer(1, frames, ctx.sampleRate);
  const source = ctx.createBufferSource();
  const gain = ctx.createGain();
  gain.gain.value = 0.0001;
  source.buffer = buffer;
  source.loop = true;
  source.connect(gain);
  gain.connect(ctx.destination);
  source.start(0);
  keepAliveSource = source;
  keepAliveGain = gain;
}

export function releaseAudioContextHold() {
  const source = keepAliveSource;
  const gain = keepAliveGain;
  keepAliveSource = null;
  keepAliveGain = null;
  if (source) {
    try {
      source.stop();
    } catch {
      /* already stopped */
    }
    try {
      source.disconnect();
    } catch {
      /* already disconnected */
    }
  }
  if (gain) {
    try {
      gain.disconnect();
    } catch {
      /* already disconnected */
    }
  }
}

export function prepareHtmlAudio(audio: HTMLAudioElement) {
  (audio as HTMLAudioElement & { playsInline?: boolean }).playsInline = true;
  audio.setAttribute('playsinline', 'true');
  audio.setAttribute('webkit-playsinline', 'true');
  audio.preload = 'auto';
  audio.removeAttribute('crossorigin');
}

/** True when HTML media events should drive the player UI (not empty/unlock/silent-hold src). */
export function shouldHandleHtmlAudioEvent(media: HTMLMediaElement | null | undefined): boolean {
  if (!media) return false;
  if (media instanceof HTMLAudioElement && isPlayerSilentHoldAudio(media)) return false;
  const src = (media.getAttribute('src') || media.currentSrc || '').trim();
  if (!src) return false;
  if (src.startsWith('data:')) return false;
  return true;
}

/** Same-origin silent WAV so iOS lock screen sees a real playing media element. */
export function assignPlayerSilentHold(audio: HTMLAudioElement) {
  if (isPlayerSilentHoldAudio(audio) && !audio.paused) return;
  prepareHtmlAudio(audio);
  audio.loop = isIosChrome();
  audio.muted = false;
  audio.volume = 0.0001;
  if (!isPlayerSilentHoldAudio(audio)) {
    audio.src = PLAYER_SILENT_HOLD_SRC;
  }
  void audio.play().catch(() => undefined);
}

/** iOS pauses the hold element when the screen locks; re-assert while Web Audio plays. */
export function ensurePlayerSilentHoldPlaying(audio: HTMLAudioElement | null | undefined) {
  if (!audio || !isPlayerSilentHoldAudio(audio)) return;
  prepareHtmlAudio(audio);
  audio.loop = isIosChrome();
  audio.muted = false;
  audio.volume = 0.0001;
  if (audio.paused) {
    void audio.play().catch(() => undefined);
  }
}

/** CriOS lock screen scrubber tracks the hold element — mirror Web Audio position (Safari uses HLS, not this). */
export function syncIosChromeHoldPosition(
  audio: HTMLAudioElement | null | undefined,
  positionSeconds: number,
): HoldSeekResult | null {
  if (!isIosChrome() || !audio || !isPlayerSilentHoldAudio(audio)) return null;
  if (!Number.isFinite(positionSeconds) || positionSeconds < 0) return null;
  const from = audio.currentTime || 0;
  const cap = Number.isFinite(audio.duration) && audio.duration > 0 ? audio.duration - 0.25 : 599;
  const target = Math.min(positionSeconds, Math.max(0, cap));
  if (Math.abs(from - target) <= 0.35) {
    return { from, target, after: from, ok: true, skipped: true };
  }
  try {
    audio.currentTime = target;
    const after = audio.currentTime || 0;
    const ok = Math.abs(after - target) <= 0.6;
    return {
      from,
      target,
      after,
      ok,
      err: ok ? undefined : 'seek_drift',
    };
  } catch (err) {
    const message = err instanceof Error ? err.message : String(err);
    return { from, target, after: from, ok: false, err: message.slice(0, 80) };
  }
}

/** CriOS: restart silent hold and report play() outcome. */
export function ensurePlayerSilentHoldPlayingWithLog(
  audio: HTMLAudioElement | null | undefined,
): Promise<{ ok: boolean; err?: string }> {
  if (!audio || !isPlayerSilentHoldAudio(audio)) {
    return Promise.resolve({ ok: false, err: 'not_hold' });
  }
  prepareHtmlAudio(audio);
  audio.loop = isIosChrome();
  audio.muted = false;
  audio.volume = 0.0001;
  if (!audio.paused) return Promise.resolve({ ok: true });
  return audio
    .play()
    .then(() => ({ ok: true }))
    .catch((err) => ({
      ok: false,
      err: err instanceof Error ? `${err.name}:${err.message}`.slice(0, 80) : String(err).slice(0, 80),
    }));
}

export function pausePlayerSilentHold(audio: HTMLAudioElement | null | undefined) {
  if (!audio || !isPlayerSilentHoldAudio(audio)) return;
  audio.pause();
}

/** Keep Web Audio from suspending during license/chunk fetch. Not the player element. */
export function holdHtmlMediaGesture() {
  if (typeof Audio === 'undefined') return;
  try {
    if (!detachedHold) {
      const hold = new Audio(silentWavDataUri());
      (hold as HTMLAudioElement & { playsInline?: boolean }).playsInline = true;
      hold.setAttribute('playsinline', 'true');
      hold.loop = true;
      hold.volume = 0.0001;
      detachedHold = hold;
    }
    void detachedHold.play().catch(() => undefined);
  } catch {
    /* detached WAV must never be assigned to the player element */
  }
}

export function releaseHtmlMediaGesture() {
  const hold = detachedHold;
  detachedHold = null;
  if (!hold) return;
  try {
    hold.pause();
    hold.removeAttribute('src');
  } catch {
    /* already released */
  }
}

export async function ensureAudioContextRunning(): Promise<AudioContext> {
  const ctx = getSharedAudioContext();
  holdAudioContext(ctx);
  try {
    await ctx.resume();
  } catch {
    /* Safari may reject resume outside a gesture */
  }
  return ctx;
}

export function installAudioContextWatch() {
  if (audioWatchInstalled || typeof document === 'undefined') return;
  audioWatchInstalled = true;
  const resume = () => {
    if (!sharedAudioContext) return;
    void sharedAudioContext.resume().catch(() => undefined);
  };
  document.addEventListener('visibilitychange', () => {
    if (!document.hidden) resume();
  });
  window.addEventListener('focus', resume);
  sharedAudioContext?.addEventListener('statechange', resume);
}

/** Call synchronously from a tap/click before any `await`. Never uses a silent MP3 data URL. */
export function unlockMediaPlayback(media?: HTMLMediaElement | null) {
  if (media) {
    if (media instanceof HTMLVideoElement) prepareHtmlVideo(media);
    else prepareHtmlAudio(media);
    media.muted = false;
  }
  try {
    const ctx = getSharedAudioContext();
    void ctx.resume();
    holdAudioContext(ctx);
  } catch {
    /* Web Audio unlock is best-effort */
  }
  holdHtmlMediaGesture();
  installAudioContextWatch();
}

export function clearHtmlAudioSrc(audio: HTMLAudioElement) {
  audio.pause();
  audio.loop = false;
  audio.removeAttribute('src');
}

export function concatBytes(parts: Uint8Array[]): Uint8Array {
  const total = parts.reduce((sum, part) => sum + part.byteLength, 0);
  const out = new Uint8Array(total);
  let offset = 0;
  for (const part of parts) {
    out.set(part, offset);
    offset += part.byteLength;
  }
  return out;
}

export function wipeBytes(bytes: Uint8Array | Uint8Array[]) {
  const list = Array.isArray(bytes) ? bytes : [bytes];
  for (const part of list) {
    try {
      part.fill(0);
    } catch {
      /* detached ArrayBuffer after decodeAudioData */
    }
  }
}

function decodeWithCallbacks(ctx: AudioContext, data: ArrayBuffer): Promise<AudioBuffer> {
  return new Promise((resolve, reject) => {
    ctx.decodeAudioData(
      data,
      resolve,
      (err) => reject(err instanceof Error ? err : new Error('Unable to decode audio.')),
    );
  });
}

export async function decodeMpegBuffer(ctx: AudioContext, data: ArrayBuffer): Promise<AudioBuffer> {
  const attempts: ArrayBuffer[] = [data.slice(0)];
  const stripped = stripToMpegSync(new Uint8Array(data));
  if (stripped.byteLength > 0 && stripped.byteLength !== data.byteLength) {
    const framed = new ArrayBuffer(stripped.byteLength);
    new Uint8Array(framed).set(stripped);
    attempts.push(framed);
  }
  let lastErr: unknown;
  for (const attempt of attempts) {
    try {
      return await ctx.decodeAudioData(attempt.slice(0));
    } catch (err) {
      lastErr = err;
    }
    try {
      return await decodeWithCallbacks(ctx, attempt.slice(0));
    } catch (err) {
      lastErr = err;
    }
  }
  throw lastErr instanceof Error ? lastErr : new Error('Unable to decode audio.');
}

export async function decodeMpegToAudioBuffer(
  ctx: AudioContext,
  data: ArrayBuffer,
): Promise<AudioBuffer> {
  if (isSafariMpegMseBroken()) {
    const { decodeMp3Software } = await import('@/lib/mp3-software-decode');
    return decodeMp3Software(ctx, data);
  }
  try {
    return await decodeMpegBuffer(ctx, data);
  } catch (nativeErr) {
    try {
      const { decodeMp3Software } = await import('@/lib/mp3-software-decode');
      return await decodeMp3Software(ctx, data);
    } catch {
      throw nativeErr;
    }
  }
}

type GraphHandlers = {
  onEnded?: () => void;
  onTime?: (seconds: number) => void;
};

/** Progressive in-memory playback for Safari/iOS. No blob: or data: MP3 URL is created. */
export class ProtectedAudioGraph {
  private ctx: AudioContext;
  private gain: GainNode;
  private buffers: AudioBuffer[] = [];
  private sources: AudioBufferSourceNode[] = [];
  private nextStartTime = 0;
  private trackStartCtxTime = 0;
  private trackOffsetAtStart = 0;
  private pausedAt = 0;
  private decodedDuration = 0;
  private pinnedDuration = 0;
  private complete = false;
  private generation = 0;
  private raf = 0;
  playing = false;
  onEnded?: () => void;
  onTime?: (seconds: number) => void;

  constructor(ctx: AudioContext, handlers: GraphHandlers = {}) {
    this.ctx = ctx;
    this.gain = ctx.createGain();
    this.gain.connect(ctx.destination);
    this.onEnded = handlers.onEnded;
    this.onTime = handlers.onTime;
  }

  get hasBuffer(): boolean {
    return this.buffers.length > 0;
  }

  get duration(): number {
    if (this.pinnedDuration > 0) return this.pinnedDuration;
    return this.decodedDuration;
  }

  /** Catalog / license duration — never grows as chunks decode. */
  setPinnedDuration(seconds: number) {
    if (Number.isFinite(seconds) && seconds > 0) {
      this.pinnedDuration = seconds;
    }
  }

  get decodedLength(): number {
    return this.decodedDuration;
  }

  get currentTime(): number {
    if (!this.hasBuffer) return 0;
    if (!this.playing) return Math.min(this.duration || this.decodedDuration, this.pausedAt);
    const elapsed = this.ctx.currentTime - this.trackStartCtxTime;
    const pos = this.trackOffsetAtStart + elapsed;
    const cap = this.duration > 0 ? this.duration : this.decodedDuration;
    return Math.min(cap, Math.max(0, pos));
  }

  setGain(volume: number, muted: boolean) {
    const next = muted ? 0 : Math.min(1, Math.max(0, volume));
    this.gain.gain.setValueAtTime(next, this.ctx.currentTime);
  }

  /** Schedule gapless PCM. Starts playback on the first buffer. */
  async appendDecoded(buffer: AudioBuffer, volume: number, muted: boolean): Promise<void> {
    this.buffers.push(buffer);
    this.decodedDuration += buffer.duration;
    this.setGain(volume, muted);

    if (!this.playing && this.buffers.length === 1) {
      await ensureAudioContextRunning();
      if (this.ctx.state !== 'running') {
        throw new Error('NotAllowedError: AudioContext is not running');
      }
      this.scheduleFromTrackPosition(0);
      return;
    }

    if (this.playing) {
      this.scheduleBufferAtEnd(buffer, this.buffers.length - 1);
    }
  }

  /** Load pre-decoded buffers from RAM cache and start playback. */
  async loadFromCache(buffers: AudioBuffer[], volume: number, muted: boolean): Promise<void> {
    this.stop(false);
    for (const buffer of buffers) {
      this.buffers.push(buffer);
      this.decodedDuration += buffer.duration;
    }
    this.setGain(volume, muted);
    await ensureAudioContextRunning();
    if (this.ctx.state !== 'running') {
      throw new Error('NotAllowedError: AudioContext is not running');
    }
    this.scheduleFromTrackPosition(0);
  }

  markComplete() {
    this.complete = true;
  }

  pause() {
    if (!this.playing) return;
    this.pausedAt = this.currentTime;
    this.stopSources(false);
    this.playing = false;
    this.stopPump();
  }

  async resume() {
    if (!this.hasBuffer || this.playing) return;
    await ensureAudioContextRunning();
    if (this.ctx.state !== 'running') {
      throw new Error('NotAllowedError: AudioContext is not running');
    }
    this.scheduleFromTrackPosition(this.pausedAt);
  }

  seek(time: number) {
    if (!this.hasBuffer) return;
    const max = this.decodedDuration;
    const next = Math.min(max, Math.max(0, time));
    const wasPlaying = this.playing;
    this.stopSources(false);
    this.pausedAt = next;
    this.onTime?.(next);
    if (wasPlaying) this.scheduleFromTrackPosition(next);
  }

  stop(clearBuffers = true) {
    this.stopSources(false);
    if (clearBuffers) {
      this.buffers = [];
      this.decodedDuration = 0;
      this.pinnedDuration = 0;
      this.complete = false;
    }
    this.pausedAt = 0;
    this.playing = false;
    this.nextStartTime = 0;
    this.stopPump();
  }

  private scheduleFromTrackPosition(trackPos: number) {
    this.stopSources(false);
    if (!this.buffers.length) return;

    const maxSeek = this.decodedDuration;
    const clamped = Math.min(maxSeek, Math.max(0, trackPos));

    let accumulated = 0;
    let startIdx = 0;
    let offsetInBuffer = 0;
    for (let i = 0; i < this.buffers.length; i += 1) {
      const dur = this.buffers[i].duration;
      if (clamped < accumulated + dur || i === this.buffers.length - 1) {
        startIdx = i;
        offsetInBuffer = Math.min(dur, Math.max(0, clamped - accumulated));
        break;
      }
      accumulated += dur;
    }

    this.generation += 1;
    const gen = this.generation;
    this.trackStartCtxTime = this.ctx.currentTime;
    this.trackOffsetAtStart = clamped;
    this.nextStartTime = this.ctx.currentTime;
    this.pausedAt = clamped;
    this.playing = true;

    for (let i = startIdx; i < this.buffers.length; i += 1) {
      const buf = this.buffers[i];
      const offset = i === startIdx ? offsetInBuffer : 0;
      const source = this.ctx.createBufferSource();
      source.buffer = buf;
      source.connect(this.gain);
      source.start(this.nextStartTime, offset);
      this.nextStartTime += buf.duration - offset;
      this.sources.push(source);

      const bufferIdx = i;
      source.onended = () => {
        if (gen !== this.generation) return;
        if (this.complete && bufferIdx === this.buffers.length - 1) {
          this.handleEnded();
        }
      };
    }
    this.startPump();
  }

  private scheduleBufferAtEnd(buffer: AudioBuffer, bufferIdx: number) {
    const gen = this.generation;
    const source = this.ctx.createBufferSource();
    source.buffer = buffer;
    source.connect(this.gain);
    source.start(this.nextStartTime);
    this.nextStartTime += buffer.duration;
    this.sources.push(source);
    source.onended = () => {
      if (gen !== this.generation) return;
      if (this.complete && bufferIdx === this.buffers.length - 1) {
        this.handleEnded();
      }
    };
  }

  private handleEnded() {
    this.playing = false;
    this.pausedAt = this.duration > 0 ? this.duration : this.decodedDuration;
    this.stopPump();
    this.onTime?.(this.pausedAt);
    this.onEnded?.();
  }

  private stopSources(_emitEnded: boolean) {
    this.generation += 1;
    for (const source of this.sources) {
      source.onended = null;
      try {
        source.stop();
      } catch {
        /* already stopped */
      }
      try {
        source.disconnect();
      } catch {
        /* already disconnected */
      }
    }
    this.sources = [];
  }

  private startPump() {
    this.stopPump();
    const tick = () => {
      if (!this.playing) return;
      this.onTime?.(this.currentTime);
      this.raf = window.requestAnimationFrame(tick);
    };
    this.raf = window.requestAnimationFrame(tick);
  }

  private stopPump() {
    if (this.raf) {
      window.cancelAnimationFrame(this.raf);
      this.raf = 0;
    }
  }
}

export function isAbortLike(err: unknown): boolean {
  if (typeof MediaError !== 'undefined' && err instanceof MediaError) {
    return err.code === MediaError.MEDIA_ERR_ABORTED || /abort/i.test(err.message || '');
  }
  const name = err instanceof Error ? err.name : '';
  const text = messageFromUnknown(err);
  return name === 'AbortError' || /operation was aborted|aborterror/i.test(text);
}

export function errorDetail(err: unknown): string {
  const name = err instanceof Error ? err.name : typeof MediaError !== 'undefined' && err instanceof MediaError ? `MediaError${err.code}` : '';
  const text = messageFromUnknown(err);
  return `${name} ${text}`.trim().slice(0, 280);
}

export function friendlyPlaybackError(err: unknown): string {
  if (isAbortLike(err)) {
    return 'Tap play again to start audio.';
  }
  const text = messageFromUnknown(err);
  if (/notallowed|user didn't interact|interact with the document|audiocontext is not running|decrypt chunk/i.test(text)) {
    return 'Tap play again to start audio.';
  }
  if (
    /operation-specific|operationerror|notsupported|sourcebuffer|mediasource|format is not supported|no supported sources|unable to decode|encodingerror/i.test(
      text,
    )
  ) {
    return 'Tap play again to start audio.';
  }
  return text.trim() || 'Playback failed. Tap play again.';
}

function messageFromUnknown(err: unknown): string {
  if (err instanceof Error && err.message) return err.message;
  if (typeof MediaError !== 'undefined' && err instanceof MediaError) {
    return err.message || `Media error ${err.code}`;
  }
  if (err && typeof err === 'object' && 'message' in err) {
    const message = (err as { message?: unknown }).message;
    if (typeof message === 'string') return message;
  }
  return typeof err === 'string' ? err : '';
}
