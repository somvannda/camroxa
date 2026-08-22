/** In-memory MP3 → PCM for Safari. Never creates a blob: or data: audio URL. */

import MPEGDecoder from '@/lib/vendor/mpg123/MPEGDecoder.js';
import { stripToMpegSync } from '@/lib/mpeg-sync';

type MpegDecoderInstance = {
  ready: Promise<void>;
  decode: (data: Uint8Array) => {
    channelData: Float32Array[];
    samplesDecoded: number;
    sampleRate: number;
  };
  free: () => void;
};

function decodedToAudioBuffer(
  ctx: AudioContext,
  decoded: { channelData: Float32Array[]; samplesDecoded: number; sampleRate: number },
): AudioBuffer {
  const buffer = ctx.createBuffer(
    decoded.channelData.length,
    decoded.samplesDecoded,
    decoded.sampleRate || ctx.sampleRate,
  );
  for (let channel = 0; channel < decoded.channelData.length; channel += 1) {
    buffer.getChannelData(channel).set(decoded.channelData[channel]);
  }
  return buffer;
}

/** Keeps one mpg123 decoder alive across encrypted chunks (leftover frames carry forward). */
export class StreamingMp3Decoder {
  private decoder: MpegDecoderInstance;
  private readyPromise: Promise<void>;
  private ctx: AudioContext;
  private firstChunk = true;
  private freed = false;

  constructor(ctx: AudioContext) {
    this.ctx = ctx;
    this.decoder = new (MPEGDecoder as unknown as new () => MpegDecoderInstance)();
    this.readyPromise = this.decoder.ready;
  }

  async ready(): Promise<void> {
    await this.readyPromise;
  }

  decodeChunk(bytes: Uint8Array): AudioBuffer | null {
    if (this.freed) return null;
    const input = this.firstChunk ? stripToMpegSync(bytes) : bytes;
    this.firstChunk = false;
    const decoded = this.decoder.decode(input);
    if (!decoded.samplesDecoded || !decoded.channelData.length) return null;
    return decodedToAudioBuffer(this.ctx, decoded);
  }

  free() {
    if (this.freed) return;
    this.freed = true;
    this.decoder.free();
  }
}

export async function decodeMp3Software(ctx: AudioContext, data: ArrayBuffer): Promise<AudioBuffer> {
  const decoder = new StreamingMp3Decoder(ctx);
  try {
    await decoder.ready();
    const buffer = decoder.decodeChunk(new Uint8Array(data));
    if (!buffer) throw new Error('Unable to decode audio.');
    return buffer;
  } finally {
    decoder.free();
  }
}
