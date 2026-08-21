/** iOS WebKit helpers: gesture unlock, blob MP3 play, Web Audio fallback. */

export function isAppleMobile(): boolean {
  if (typeof navigator === 'undefined') return false;
  const ua = navigator.userAgent || '';
  if (/iPhone|iPad|iPod/i.test(ua)) return true;
  return navigator.platform === 'MacIntel' && (navigator.maxTouchPoints || 0) > 1;
}

export function isIosPackagedPlayback(): boolean {
  if (typeof window === 'undefined') return false;
  if (isAppleMobile()) return true;
  const ua = navigator.userAgent || '';
  if (/CriOS|FxiOS|EdgiOS/i.test(ua)) return true;
  try {
    if (window.localStorage.getItem('camxora-force-ios-player') === '1') return true;
    if (new URLSearchParams(window.location.search).get('iosPlayer') === '1') return true;
  } catch {
    /* private mode */
  }
  return false;
}

let sharedAudioContext: AudioContext | null = null;
let silentWavUri: string | null = null;

function audioContextCtor(): typeof AudioContext | undefined {
  if (typeof window === 'undefined') return undefined;
  return (
    window.AudioContext ||
    (window as unknown as { webkitAudioContext?: typeof AudioContext }).webkitAudioContext
  );
}

export function getSharedAudioContext(): AudioContext | null {
  const Ctor = audioContextCtor();
  if (!Ctor) return null;
  if (!sharedAudioContext) {
    sharedAudioContext = new Ctor();
  }
  return sharedAudioContext;
}

export function resumeSharedAudioContext(): void {
  const ctx = getSharedAudioContext();
  if (!ctx) return;
  void ctx.resume();
  try {
    const frames = Math.max(1, Math.floor(ctx.sampleRate / 20));
    const buffer = ctx.createBuffer(1, frames, ctx.sampleRate);
    const source = ctx.createBufferSource();
    const gain = ctx.createGain();
    gain.gain.value = 0.0001;
    source.buffer = buffer;
    source.connect(gain);
    gain.connect(ctx.destination);
    source.start(0);
  } catch {
    /* ignore */
  }
}

function silentWavDataUri(): string {
  if (silentWavUri) return silentWavUri;
  const sampleRate = 8000;
  const samples = sampleRate;
  const dataSize = samples;
  const buffer = new ArrayBuffer(44 + dataSize);
  const view = new DataView(buffer);
  const writeStr = (offset: number, text: string) => {
    for (let i = 0; i < text.length; i += 1) {
      view.setUint8(offset + i, text.charCodeAt(i));
    }
  };
  writeStr(0, 'RIFF');
  view.setUint32(4, 36 + dataSize, true);
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
  view.setUint32(40, dataSize, true);
  for (let i = 0; i < dataSize; i += 1) {
    view.setUint8(44 + i, 128);
  }
  const bytes = new Uint8Array(buffer);
  let binary = '';
  for (let i = 0; i < bytes.length; i += 1) {
    binary += String.fromCharCode(bytes[i]);
  }
  silentWavUri = `data:audio/wav;base64,${btoa(binary)}`;
  return silentWavUri;
}

export function startSilentHold(audio: HTMLAudioElement): void {
  audio.setAttribute('playsinline', 'true');
  audio.setAttribute('webkit-playsinline', 'true');
  audio.preload = 'auto';
  audio.loop = true;
  audio.removeAttribute('crossorigin');
  audio.src = silentWavDataUri();
  void audio.play().catch(() => undefined);
}

export class WebAudioPlayback {
  private readonly ctx: AudioContext;
  private readonly gain: GainNode;
  private readonly buffer: AudioBuffer;
  private source: AudioBufferSourceNode | null = null;
  private offset = 0;
  private startedAt = 0;
  private stopping = false;
  private raf = 0;
  playing = false;
  onEnded: (() => void) | null = null;
  onTime: ((currentTime: number, duration: number) => void) | null = null;

  constructor(ctx: AudioContext, buffer: AudioBuffer, volume: number) {
    this.ctx = ctx;
    this.buffer = buffer;
    this.gain = ctx.createGain();
    this.gain.gain.value = volume;
    this.gain.connect(ctx.destination);
  }

  static async fromMp3(mp3: ArrayBuffer, volume: number): Promise<WebAudioPlayback | null> {
    const ctx = getSharedAudioContext();
    if (!ctx) return null;
    await ctx.resume();
    const decoded = await ctx.decodeAudioData(mp3.slice(0));
    return new WebAudioPlayback(ctx, decoded, volume);
  }

  get duration(): number {
    return this.buffer.duration;
  }

  get currentTime(): number {
    if (!this.playing) return this.offset;
    return Math.min(this.buffer.duration, this.offset + (this.ctx.currentTime - this.startedAt));
  }

  start(offset = 0): void {
    this.stopSource();
    this.stopping = false;
    const safeOffset = Math.min(Math.max(0, offset), Math.max(0, this.buffer.duration - 0.05));
    const source = this.ctx.createBufferSource();
    source.buffer = this.buffer;
    source.connect(this.gain);
    source.onended = () => {
      if (this.stopping) return;
      this.playing = false;
      this.offset = this.buffer.duration;
      this.stopRaf();
      this.onEnded?.();
    };
    source.start(0, safeOffset);
    this.source = source;
    this.offset = safeOffset;
    this.startedAt = this.ctx.currentTime;
    this.playing = true;
    this.startRaf();
  }

  pause(): void {
    this.offset = this.currentTime;
    this.playing = false;
    this.stopSource();
    this.stopRaf();
  }

  seek(time: number): void {
    const next = Math.min(Math.max(0, time), this.buffer.duration);
    if (this.playing) {
      this.start(next);
      return;
    }
    this.offset = next;
    this.onTime?.(this.offset, this.buffer.duration);
  }

  setVolume(volume: number): void {
    this.gain.gain.value = Math.min(1, Math.max(0, volume));
  }

  stop(): void {
    this.playing = false;
    this.stopSource();
    this.stopRaf();
    this.onEnded = null;
    this.onTime = null;
  }

  private stopSource(): void {
    this.stopping = true;
    if (this.source) {
      try {
        this.source.onended = null;
        this.source.stop();
      } catch {
        /* already stopped */
      }
      this.source.disconnect();
      this.source = null;
    }
  }

  private startRaf(): void {
    this.stopRaf();
    const tick = () => {
      if (!this.playing) return;
      this.onTime?.(this.currentTime, this.buffer.duration);
      this.raf = window.requestAnimationFrame(tick);
    };
    this.raf = window.requestAnimationFrame(tick);
  }

  private stopRaf(): void {
    if (this.raf) {
      window.cancelAnimationFrame(this.raf);
      this.raf = 0;
    }
  }
}
