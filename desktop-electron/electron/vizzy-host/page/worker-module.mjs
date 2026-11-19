/* Module worker probe.
 * Vite builds the Rea FFT worker as an ES module worker, so the host must
 * support `new Worker(url, { type: "module" })` as well as classic workers.
 */
/* global self, WebAssembly */

self.onmessage = (event) => {
  const sab = event.data && event.data.sab;
  let atomics = false;
  if (sab instanceof SharedArrayBuffer) {
    const view = new Int32Array(sab);
    Atomics.store(view, 0, 7);
    atomics = Atomics.load(view, 0) === 7;
  }
  self.postMessage({
    kind: "module",
    crossOriginIsolated: self.crossOriginIsolated === true,
    sharedArrayBuffer: typeof SharedArrayBuffer === "function",
    atomics,
    wasm: typeof WebAssembly === "object",
    url: self.location.href,
  });
};
