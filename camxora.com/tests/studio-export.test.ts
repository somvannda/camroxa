import { describe, expect, it } from "vitest";

import { encodeWav } from "@/lib/studio-export";

function readString(bytes: Uint8Array, offset: number, length: number): string {
  return String.fromCharCode(...bytes.slice(offset, offset + length));
}

describe("encodeWav", () => {
  it("writes a valid 16-bit stereo RIFF header", () => {
    const frames = 100;
    const left = new Float32Array(frames);
    const right = new Float32Array(frames);
    const bytes = encodeWav([left, right], 44100);
    const view = new DataView(bytes.buffer);

    expect(readString(bytes, 0, 4)).toBe("RIFF");
    expect(readString(bytes, 8, 4)).toBe("WAVE");
    expect(readString(bytes, 12, 4)).toBe("fmt ");
    expect(readString(bytes, 36, 4)).toBe("data");
    expect(view.getUint16(20, true)).toBe(1); // PCM
    expect(view.getUint16(22, true)).toBe(2); // channels
    expect(view.getUint32(24, true)).toBe(44100);
    expect(view.getUint16(34, true)).toBe(16); // bit depth
    expect(view.getUint32(40, true)).toBe(frames * 2 * 2);
    expect(bytes.length).toBe(44 + frames * 2 * 2);
  });

  it("sizes the file from the sample count, not a guess", () => {
    const seconds = 2;
    const rate = 44100;
    const frames = seconds * rate;
    const mono = new Float32Array(frames);
    const bytes = encodeWav([mono], rate);
    expect(bytes.length).toBe(44 + frames * 2);
    expect(new DataView(bytes.buffer).getUint32(40, true)).toBe(frames * 2);
  });

  it("round-trips sample values and clamps out-of-range input", () => {
    const values = new Float32Array([0, 0.5, -0.5, 1.8, -1.8]);
    const bytes = encodeWav([values], 8000);
    const view = new DataView(bytes.buffer);
    const read = (index: number) => view.getInt16(44 + index * 2, true);

    expect(read(0)).toBe(0);
    // setInt16 truncates toward zero, so allow one LSB either way.
    expect(Math.abs(read(1) - 0.5 * 0x7fff)).toBeLessThanOrEqual(1);
    expect(Math.abs(read(2) - -0.5 * 0x8000)).toBeLessThanOrEqual(1);
    expect(read(3)).toBe(0x7fff); // clamped, not wrapped
    expect(read(4)).toBe(-0x8000);
  });
});
