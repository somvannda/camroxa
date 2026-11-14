/**
 * MP3 encoding for Studio exports.
 *
 * The classic editor shipped `Mp3Encoder` from `@breezystack/lamejs`; the main shell only
 * offered WAV. This module keeps the encoder behind a dynamic import so the studio route
 * does not pay for it until someone exports an MP3.
 */

import { Mp3Encoder } from "@breezystack/lamejs";

/** Encode an offline render to MP3. Returns raw bytes, ready for a Blob. */
export async function encodeMp3(buffer: AudioBuffer, kbps = 192): Promise<Uint8Array> {
  const channels = Math.min(2, buffer.numberOfChannels);
  const encoder = new Mp3Encoder(channels, buffer.sampleRate, kbps);
  const left = buffer.getChannelData(0);
  const right = channels > 1 ? buffer.getChannelData(1) : left;
  const blockSize = 1152;
  const leftPcm = new Int16Array(blockSize);
  const rightPcm = new Int16Array(blockSize);
  const chunks: Uint8Array[] = [];

  const toPcm = (source: Float32Array, target: Int16Array, offset: number, length: number) => {
    for (let index = 0; index < length; index += 1) {
      const sample = Math.max(-1, Math.min(1, source[offset + index] ?? 0));
      target[index] = sample < 0 ? sample * 0x8000 : sample * 0x7fff;
    }
  };

  for (let offset = 0; offset < buffer.length; offset += blockSize) {
    const length = Math.min(blockSize, buffer.length - offset);
    toPcm(left, leftPcm, offset, length);
    if (channels > 1) toPcm(right, rightPcm, offset, length);
    const chunk =
      channels > 1
        ? encoder.encodeBuffer(leftPcm.subarray(0, length), rightPcm.subarray(0, length))
        : encoder.encodeBuffer(leftPcm.subarray(0, length));
    if (chunk.length > 0) chunks.push(new Uint8Array(chunk));
  }
  const tail = encoder.flush();
  if (tail.length > 0) chunks.push(new Uint8Array(tail));

  const total = chunks.reduce((size, chunk) => size + chunk.length, 0);
  const output = new Uint8Array(total);
  let cursor = 0;
  for (const chunk of chunks) {
    output.set(chunk, cursor);
    cursor += chunk.length;
  }
  return output;
}
