/* Host spike probes.
 *
 * Everything here runs inside the hosted page, exactly as the Vizzy editor
 * would. The result is published on `window.__vizzySpikeResult` for the main
 * process (and printed to the console for a direct launch).
 */
/* global window, document, console, fetch, Worker, WebAssembly, performance, navigator, setTimeout, clearTimeout */

const WASM_ADD = Uint8Array.from([
  0, 97, 115, 109, 1, 0, 0, 0, 1, 7, 1, 96, 2, 127, 127, 1, 127, 3, 2, 1, 0, 7, 7, 1, 3, 97, 100,
  100, 0, 0, 10, 9, 1, 7, 0, 32, 0, 32, 1, 106, 11,
]);

// (func (export "probe") (result v128) (v128.const i32x4 0 0 0 0))
// A module that only validates on a WebAssembly SIMD-capable engine.
const WASM_SIMD = Uint8Array.from([
  0, 97, 115, 109, 1, 0, 0, 0, 1, 5, 1, 96, 0, 1, 123, 3, 2, 1, 0, 7, 9, 1, 5, 112, 114, 111, 98,
  101, 0, 0, 10, 22, 1, 20, 0, 253, 12, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 11,
]);

function errorText(error) {
  if (error instanceof Error) return error.message;
  return String(error);
}

async function readResponseHeaders() {
  try {
    const response = await fetch(window.location.href, { cache: "no-store" });
    return {
      ok: response.ok,
      status: response.status,
      coop: response.headers.get("cross-origin-opener-policy"),
      coep: response.headers.get("cross-origin-embedder-policy"),
      corp: response.headers.get("cross-origin-resource-policy"),
      contentType: response.headers.get("content-type"),
      csp: response.headers.get("content-security-policy"),
    };
  } catch (error) {
    return { ok: false, error: errorText(error) };
  }
}

function probeWebGL2() {
  try {
    const canvas = document.createElement("canvas");
    canvas.width = 32;
    canvas.height = 32;
    const gl = canvas.getContext("webgl2", { antialias: false, preserveDrawingBuffer: true });
    if (!gl) return { ok: false, reason: "getContext('webgl2') returned null" };

    gl.clearColor(0.25, 0.5, 0.75, 1);
    gl.clear(gl.COLOR_BUFFER_BIT);
    const pixel = new Uint8Array(4);
    gl.readPixels(0, 0, 1, 1, gl.RGBA, gl.UNSIGNED_BYTE, pixel);
    const drew =
      Math.abs(pixel[0] - 64) <= 2 &&
      Math.abs(pixel[1] - 128) <= 2 &&
      Math.abs(pixel[2] - 191) <= 2 &&
      pixel[3] === 255;

    const debug = gl.getExtension("WEBGL_debug_renderer_info");
    return {
      ok: true,
      drew,
      version: gl.getParameter(gl.VERSION),
      shadingLanguage: gl.getParameter(gl.SHADING_LANGUAGE_VERSION),
      vendor: gl.getParameter(gl.VENDOR),
      renderer: gl.getParameter(gl.RENDERER),
      unmaskedVendor: debug ? gl.getParameter(debug.UNMASKED_VENDOR_WEBGL) : null,
      unmaskedRenderer: debug ? gl.getParameter(debug.UNMASKED_RENDERER_WEBGL) : null,
      maxTextureSize: gl.getParameter(gl.MAX_TEXTURE_SIZE),
      maxRenderbufferSize: gl.getParameter(gl.MAX_RENDERBUFFER_SIZE),
      floatLinear: Boolean(gl.getExtension("OES_texture_float_linear")),
      colorBufferFloat: Boolean(gl.getExtension("EXT_color_buffer_float")),
      pixel: Array.from(pixel),
    };
  } catch (error) {
    return { ok: false, reason: errorText(error) };
  }
}

function runWorker(scriptUrl, type, sab) {
  return new Promise((resolve) => {
    const started = performance.now();
    let settled = false;
    let worker = null;
    const finish = (value) => {
      if (settled) return;
      settled = true;
      resolve({ ...value, elapsedMs: Math.round(performance.now() - started) });
      if (worker) worker.terminate();
    };

    try {
      worker =
        type === "module"
          ? new Worker(scriptUrl, { type: "module" })
          : new Worker(scriptUrl);
    } catch (error) {
      finish({ ok: false, error: errorText(error) });
      return;
    }

    const timer = setTimeout(() => finish({ ok: false, error: "worker timeout" }), 8000);
    worker.onmessage = (event) => {
      clearTimeout(timer);
      finish({ ok: true, reply: event.data });
    };
    worker.onerror = (event) => {
      clearTimeout(timer);
      finish({ ok: false, error: event.message || "worker error" });
    };
    worker.postMessage({ sab });
  });
}

function probeWasm() {
  let instantiated = null;
  let instantiateError = null;
  try {
    const module = new WebAssembly.Module(WASM_ADD);
    const instance = new WebAssembly.Instance(module);
    instantiated = instance.exports.add(1, 2);
  } catch (error) {
    instantiateError = errorText(error);
  }

  const basicValid = WebAssembly.validate(WASM_ADD);
  const simdValid = WebAssembly.validate(WASM_SIMD);
  return {
    validate: basicValid,
    instantiate: instantiated,
    instantiateError,
    simdSupported: simdValid,
    basic: { valid: basicValid, add: instantiated },
    simd: { valid: simdValid },
  };
}

function probeSharedMemory() {
  const available = typeof SharedArrayBuffer === "function";
  if (!available) return { available, works: false, reason: "SharedArrayBuffer is not exposed" };
  try {
    const sab = new SharedArrayBuffer(16);
    const view = new Int32Array(sab);
    Atomics.store(view, 0, 11);
    return { available, works: Atomics.load(view, 0) === 11, byteLength: sab.byteLength };
  } catch (error) {
    return { available, works: false, reason: errorText(error) };
  }
}

function render(result) {
  const tbody = document.getElementById("checks");
  const raw = document.getElementById("raw");
  const dot = document.getElementById("status-dot");
  const text = document.getElementById("status-text");
  if (!tbody || !raw || !dot || !text) return;

  const rows = [
    ["Location", result.page.url],
    ["Protocol", result.page.protocol],
    ["Secure context", String(result.page.isSecureContext)],
    ["COOP", String(result.responseHeaders.coop)],
    ["COEP", String(result.responseHeaders.coep)],
    ["CORP", String(result.responseHeaders.corp)],
    [
      "crossOriginIsolated",
      result.crossOriginIsolated ? "true" : "FALSE",
    ],
    [
      "SharedArrayBuffer",
      result.sharedArrayBuffer ? `function (works: ${result.sharedMemoryWorks})` : "undefined",
    ],
    [
      "Cross-thread memory",
      `classic=${String(result.crossThread.classic)} · module=${String(result.crossThread.module)}`,
    ],
    [
      "WebGL2",
      result.webgl2.ok
        ? `${result.webgl2.renderer} · draw=${result.webgl2.drew}`
        : `FALSE (${result.webgl2.reason})`,
    ],
    [
      "Worker (classic)",
      result.worker.ok
        ? `ok · isolated=${result.worker.reply.crossOriginIsolated} · atomics=${result.worker.reply.atomics}`
        : `FALSE (${result.worker.error})`,
    ],
    [
      "Worker (module)",
      result.moduleWorker.ok
        ? `ok · isolated=${result.moduleWorker.reply.crossOriginIsolated}`
        : `FALSE (${result.moduleWorker.error})`,
    ],
    [
      "WebAssembly",
      `validate=${result.wasm.validate} · add=${result.wasm.instantiate} · simd=${result.wasm.simdSupported}`,
    ],
  ];

  for (const [name, value] of rows) {
    const tr = document.createElement("tr");
    const nameCell = document.createElement("td");
    nameCell.className = "name";
    nameCell.textContent = name;
    const valueCell = document.createElement("td");
    valueCell.className = "value";
    const good = !String(value).startsWith("FALSE") && !String(value).startsWith("undefined");
    valueCell.classList.add(good ? "ok" : "bad");
    valueCell.textContent = value;
    tr.append(nameCell, valueCell);
    tbody.append(tr);
  }

  dot.classList.add(result.ok ? "ok" : "bad");
  text.textContent = result.ok ? "all required checks passed" : "required checks failed";
  raw.textContent = JSON.stringify(result, null, 2);
}

async function main() {
  const responseHeaders = await readResponseHeaders();
  const sharedMemory = probeSharedMemory();

  // One buffer per worker: two workers racing on the same cells makes the
  // read-back probe non-deterministic. Separate buffers also prove that the
  // page and each worker see the same memory, not a structured-clone copy.
  const classicBuffer = sharedMemory.available ? new SharedArrayBuffer(16) : null;
  const moduleBuffer = sharedMemory.available ? new SharedArrayBuffer(16) : null;

  const [worker, moduleWorker] = await Promise.all([
    runWorker("./worker.js", "classic", classicBuffer),
    runWorker("./worker-module.mjs", "module", moduleBuffer),
  ]);

  const crossThread = {
    classic: classicBuffer ? Atomics.load(new Int32Array(classicBuffer), 0) : null,
    module: moduleBuffer ? Atomics.load(new Int32Array(moduleBuffer), 0) : null,
  };
  const sharedMemoryWorks =
    sharedMemory.works && crossThread.classic === 42 && crossThread.module === 7;

  const result = {
    page: {
      url: window.location.href,
      protocol: window.location.protocol,
      origin: window.location.origin,
      isSecureContext: window.isSecureContext === true,
      userAgent: navigator.userAgent,
      hardwareConcurrency: navigator.hardwareConcurrency,
    },
    responseHeaders,
    crossOriginIsolated: window.crossOriginIsolated === true,
    sharedArrayBuffer: typeof SharedArrayBuffer === "function",
    sharedMemoryWorks,
    sharedMemory,
    crossThread,
    webgl2: probeWebGL2(),
    worker,
    moduleWorker,
    wasm: probeWasm(),
  };

  result.required = {
    crossOriginIsolated: result.crossOriginIsolated,
    sharedArrayBuffer: result.sharedArrayBuffer,
    sharedMemoryWorks: result.sharedMemoryWorks,
    webgl2: result.webgl2.ok && result.webgl2.drew === true,
    worker: result.worker.ok && result.worker.reply.crossOriginIsolated === true,
    workerAtomics: crossThread.classic === 42 && crossThread.module === 7,
    moduleWorker: result.moduleWorker.ok && result.moduleWorker.reply.crossOriginIsolated === true,
    wasm: result.wasm.validate === true,
    wasmSimd: result.wasm.simdSupported === true,
  };
  result.ok = Object.values(result.required).every(Boolean);

  window.__vizzySpikeResult = result;
  render(result);
  console.log("VIZZY_SPIKE " + JSON.stringify(result));
}

main().catch((error) => {
  const failure = {
    ok: false,
    fatal: errorText(error),
    crossOriginIsolated: window.crossOriginIsolated === true,
  };
  window.__vizzySpikeResult = failure;
  console.error("VIZZY_SPIKE_FAILED", failure);
});
