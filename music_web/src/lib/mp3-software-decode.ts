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

export async function decodeMp3Software(ctx: AudioContext, data: ArrayBuffer): Promise<AudioBuffer> {
  const decoder = new (MPEGDecoder as unknown as new () => MpegDecoderInstance)();
  try {
    await decoder.ready;
    const framed = stripToMpegSync(new Uint8Array(data));
    const decoded = decoder.decode(framed);
    if (!decoded.samplesDecoded || !decoded.channelData.length) {
      throw new Error('Unable to decode audio.');
    }
    const buffer = ctx.createBuffer(
      decoded.channelData.length,
      decoded.samplesDecoded,
      decoded.sampleRate || ctx.sampleRate,
    );
    for (let channel = 0; channel < decoded.channelData.length; channel += 1) {
      buffer.getChannelData(channel).set(decoded.channelData[channel]);
    }
    return buffer;
  } finally {
    decoder.free();
  }
}
