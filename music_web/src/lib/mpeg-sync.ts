/** Find the first MPEG frame. Safari decodeAudioData often rejects ID3-prefixed MP3. */

export function stripToMpegSync(bytes: Uint8Array): Uint8Array {
  let start = 0;
  if (bytes.byteLength >= 10 && bytes[0] === 0x49 && bytes[1] === 0x44 && bytes[2] === 0x33) {
    const size =
      ((bytes[6] & 0x7f) << 21) |
      ((bytes[7] & 0x7f) << 14) |
      ((bytes[8] & 0x7f) << 7) |
      (bytes[9] & 0x7f);
    start = Math.min(bytes.byteLength, 10 + size);
  }
  for (let i = start; i + 1 < bytes.byteLength; i += 1) {
    if (bytes[i] === 0xff && (bytes[i + 1] & 0xe0) === 0xe0) {
      return bytes.subarray(i);
    }
  }
  return start > 0 ? bytes.subarray(start) : bytes;
}
