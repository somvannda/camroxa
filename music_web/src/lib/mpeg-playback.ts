/** Protected MPEG playback. Never create a downloadable audio/mpeg blob or data URL. */

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

function silentWavDataUri(): string {
  if (silentWavUri) return silentWavUri;
  const sampleRate = 8000;
  const samples = Math.max(1, Math.floor(sampleRate / 5));
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
  let binary = '';
  const bytes = new Uint8Array(buffer);
  for (let i = 0; i < bytes.length; i += 1) {
    binary += String.fromCharCode(bytes[i]);
  }
  silentWavUri = `data:audio/wav;base64,${btoa(binary)}`;
  return silentWavUri;
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

/** True when HTML audio events should drive the player UI (not empty/unlock src). */
export function shouldHandleHtmlAudioEvent(audio: HTMLAudioElement | null | undefined): boolean {
  if (!audio) return false;
  const src = (audio.getAttribute('src') || audio.src || '').trim();
  if (!src) return false;
  if (src.startsWith('data:')) return false;
  return true;
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
export function unlockMediaPlayback(audio?: HTMLAudioElement | null) {
  if (audio) {
    prepareHtmlAudio(audio);
    audio.muted = false;
    audio.loop = false;
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

/** In-memory playback for Safari/iOS. No blob: or data: MP3 URL is created. */
export class ProtectedAudioGraph {
  private ctx: AudioContext;
  private gain: GainNode;
  private source: AudioBufferSourceNode | null = null;
  private buffer: AudioBuffer | null = null;
  private startCtxTime = 0;
  private pausedAt = 0;
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
    return this.buffer != null;
  }

  get duration(): number {
    return this.buffer?.duration ?? 0;
  }

  get currentTime(): number {
    if (!this.buffer) return 0;
    if (!this.playing) return Math.min(this.duration, this.pausedAt);
    const elapsed = this.ctx.currentTime - this.startCtxTime;
    return Math.min(this.duration, Math.max(0, this.pausedAt + elapsed));
  }

  setGain(volume: number, muted: boolean) {
    const next = muted ? 0 : Math.min(1, Math.max(0, volume));
    this.gain.gain.setValueAtTime(next, this.ctx.currentTime);
  }

  async loadDecoded(buffer: AudioBuffer, volume: number, muted: boolean) {
    this.stopSource(false);
    this.buffer = buffer;
    this.pausedAt = 0;
    this.setGain(volume, muted);
    await ensureAudioContextRunning();
    if (this.ctx.state !== 'running') {
      throw new Error('NotAllowedError: AudioContext is not running');
    }
    this.startSource(0);
  }

  pause() {
    if (!this.playing) return;
    this.pausedAt = this.currentTime;
    this.stopSource(false);
    this.playing = false;
    this.stopPump();
  }

  async resume() {
    if (!this.buffer || this.playing) return;
    await ensureAudioContextRunning();
    if (this.ctx.state !== 'running') {
      throw new Error('NotAllowedError: AudioContext is not running');
    }
    this.startSource(this.pausedAt);
  }

  seek(time: number) {
    if (!this.buffer) return;
    const next = Math.min(this.duration, Math.max(0, time));
    const wasPlaying = this.playing;
    this.stopSource(false);
    this.pausedAt = next;
    this.onTime?.(next);
    if (wasPlaying) this.startSource(next);
  }

  stop() {
    this.stopSource(false);
    this.buffer = null;
    this.pausedAt = 0;
    this.playing = false;
    this.stopPump();
  }

  private startSource(offset: number) {
    if (!this.buffer) return;
    this.stopSource(false);
    const gen = this.generation;
    const source = this.ctx.createBufferSource();
    source.buffer = this.buffer;
    source.connect(this.gain);
    source.onended = () => {
      if (gen !== this.generation) return;
      this.playing = false;
      this.pausedAt = this.duration;
      this.stopPump();
      this.onTime?.(this.duration);
      this.onEnded?.();
    };
    this.source = source;
    this.pausedAt = offset;
    this.startCtxTime = this.ctx.currentTime;
    this.playing = true;
    source.start(0, offset);
    this.startPump();
  }

  private stopSource(emitEnded: boolean) {
    this.generation += 1;
    const source = this.source;
    this.source = null;
    if (source) {
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
    if (emitEnded) this.onEnded?.();
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
