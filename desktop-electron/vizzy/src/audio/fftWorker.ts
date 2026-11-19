/// <reference lib="webworker" />
/**
 * FFT sub-transform worker.
 *
 * Receives a half-length slice of the signal in a SharedArrayBuffer, performs
 * the transform in place, then reports back. Used by the threaded tier.
 */

import { fftInPlace } from "./fft";

interface WorkMessage {
  signal: SharedArrayBuffer;
  ready: SharedArrayBuffer;
  real: ArrayBuffer;
  imag: ArrayBuffer;
  n: number;
  slot: number;
}

self.onmessage = (event: MessageEvent<WorkMessage>) => {
  const { signal, n, slot } = event.data;
  const real = new Float32Array(signal, 0, n);
  const imag = new Float32Array(signal, n * 4, n);

  fftInPlace(real, imag);

  const ready = new Int32Array(event.data.ready);
  Atomics.add(ready, 0, 1);
  (self as unknown as Worker).postMessage({ slot, done: true });
};
