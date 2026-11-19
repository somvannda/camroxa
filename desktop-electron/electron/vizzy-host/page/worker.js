/* Classic worker used by the host spike.
 * It must be loaded from a URL (not a Blob) so the custom protocol's relative
 * resolution and MIME handling are exercised the same way the real editor's
 * FFT worker will be.
 */
/* global self, WebAssembly, navigator */

self.onmessage = (event) => {
  const sab = event.data && event.data.sab;
  let atomics = false;
  if (sab instanceof SharedArrayBuffer) {
    const view = new Int32Array(sab);
    Atomics.store(view, 0, 42);
    atomics = Atomics.load(view, 0) === 42;
  }
  self.postMessage({
    kind: "classic",
    crossOriginIsolated: self.crossOriginIsolated === true,
    sharedArrayBuffer: typeof SharedArrayBuffer === "function",
    atomics,
    wasm: typeof WebAssembly === "object",
    hardwareConcurrency: navigator.hardwareConcurrency,
    url: self.location.href,
  });
};
