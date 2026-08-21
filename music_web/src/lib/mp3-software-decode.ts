/** In-memory MP3 → PCM for Safari/Firefox. Never creates a blob: or data: audio URL. */

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

function pcmToAudioBuffer(
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

export class Mp3PcmDecoder {
  private decoder: MpegDecoderInstance | null = null;
  private stripped = false;

  async ensure(): Promise<void> {
    if (this.decoder) return;
    const decoder = new (MPEGDecoder as unknown as new () => MpegDecoderInstance)();
    await decoder.ready;
    this.decoder = decoder;
  }

  decodeChunk(ctx: AudioContext, data: Uint8Array): AudioBuffer | null {
    if (!this.decoder) throw new Error('MP3 decoder is not ready.');
    const framed = this.stripped ? data : stripToMpegSync(data);
    this.stripped = true;
    if (!framed.byteLength) return null;
    const decoded = this.decoder.decode(framed);
    if (!decoded.samplesDecoded || !decoded.channelData.length) return null;
    return pcmToAudioBuffer(ctx, decoded);
  }

  free() {
    const decoder = this.decoder;
    this.decoder = null;
    this.stripped = false;
    if (decoder) {
      try {
        decoder.free();
      } catch {
        /* already freed */
      }
    }
  }
}

export async function decodeMp3Software(ctx: AudioContext, data: ArrayBuffer): Promise<AudioBuffer> {
  const stream = new Mp3PcmDecoder();
  try {
    await stream.ensure();
    const buffer = stream.decodeChunk(ctx, new Uint8Array(data));
    if (!buffer) throw new Error('Unable to decode audio.');
    return buffer;
  } finally {
    stream.free();
  }
}
