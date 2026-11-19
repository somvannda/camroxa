# Vizzy — Host Spike (P7 prerequisite)

> **Document ID:** CAMXORA-ED-VZ-SP-01
> **Version:** 1.0.0
> **Status:** Verified — spike complete, no production wiring
> **Scope:** P7 host feasibility only
> **Last updated:** 2026-11-19

This spike answers one load-bearing question before any Vizzy port work:

> **Can the Electron shell host a Vizzy-like page with cross-origin isolation,
> SharedArrayBuffer, WebGL2, module workers and WebAssembly, using a custom protocol or a
> tokenised loopback server — and which transport should ship?**

Answer: **yes, both work; ship the custom `camxora-vizzy://` scheme and keep the loopback
server as a tested fallback.**

Nothing in this spike is wired into `electron/main.ts`, `electron/preload.ts`,
`electron/ipc/**`, `src/app.tsx` or the shell. It is a self-contained probe plus a bridge
design skeleton.

---

## 1. What was tested

The hosted page (`electron/vizzy-host/page/`) runs this matrix inside a real
`WebContentsView`, with `contextIsolation: true`, `sandbox: true`, `nodeIntegration: false`:

| Probe | Assertion |
|---|---|
| `crossOriginIsolated` | `=== true` on the document |
| `SharedArrayBuffer` | constructor exists, allocation works, `Atomics` store/load works |
| Cross-thread memory | the page reads `42` written by a classic worker and `7` written by a module worker (same buffer, not a clone) |
| COOP / COEP / CORP | the page fetches its own URL and reports the delivered header values |
| WebGL2 | `getContext('webgl2')` non-null, `clear` + `readPixels` returns the exact expected pixel, extensions and GPU reported |
| Worker (classic) | `new Worker("./worker.js")` loads from a URL, replies, and reports `crossOriginIsolated === true` inside the worker |
| Worker (module) | `new Worker("./worker-module.mjs", { type: "module" })` — the shape Vite emits for the Rea FFT worker |
| WebAssembly | `WebAssembly.validate` + instantiate (`add(1,2) === 3`) |
| WebAssembly SIMD | a `v128` module validates (`simdSupported === true`) |

Both transports serve byte-identical assets with identical headers, so a difference in
results is a transport difference, not a page difference.

### 1.1 Transports

| Mode | URL | Mechanism |
|---|---|---|
| `protocol` | `camxora-vizzy://vizzy/index.html` | privileged custom scheme (`standard`, `secure`, `supportFetchAPI`, `stream`, `corsEnabled`, `codeCache`) + `protocol.handle` |
| `loopback` | `http://127.0.0.1:<ephemeral>/t/<32-hex-token>/index.html` | `node:http`, bound to `127.0.0.1`, token required on every request, GET/HEAD only |

Both set, on every response including errors:

```
Cross-Origin-Opener-Policy: same-origin
Cross-Origin-Embedder-Policy: require-corp
Cross-Origin-Resource-Policy: cross-origin
```

plus `Content-Security-Policy` (`default-src 'self'; script-src 'self' 'wasm-unsafe-eval'; worker-src 'self'; …`),
`X-Content-Type-Options: nosniff` and `Cache-Control: no-store`.

---

## 2. Environment

| Field | Value |
|---|---|
| OS | Windows, `win32-x64` |
| Electron | 45.4.1 |
| Chromium | 156.0.8078.100 |
| Node (main process) | 24.22.3 |
| GPU (ANGLE/D3D11) | NVIDIA GeForce RTX 3060, `D3D11 vs_5_0 ps_5_0` |
| `maxTextureSize` / `maxRenderbufferSize` | 16384 / 16384 |
| `OES_texture_float_linear` / `EXT_color_buffer_float` | both available |
| Logical cores | 32 |

---

## 3. How it is measured

1. `scripts/vizzy-host-spike.mjs` bundles `electron/vizzy-host/spike-main.ts` with the
   existing esbuild dev dependency into `dist-electron/vizzy-host-spike/spike-main.cjs`.
2. Playwright's `_electron` launches that file once per transport, with a disposable
   `userData` directory under the OS temp folder.
3. The spike main installs the transport, creates a `BrowserWindow` shell containing a
   `WebContentsView` (the same container P7 will use), and loads the page.
4. The page publishes its full result on `window.__vizzySpikeResult` and also logs
   `VIZZY_SPIKE <json>`.
5. The main process reads it with `webContents.executeJavaScript("window.__vizzySpikeResult ?? null")`
   — the same hook the P7 E2E harness plans to use for `window.__vizzyTest` — and publishes a
   JSON envelope on `globalThis.__vizzySpike`.
6. Playwright reads the envelope through `app.evaluate`, prints the report as JSON and exits
   non-zero if any required check fails or a header is missing.

Required checks: `crossOriginIsolated`, `sharedArrayBuffer`, `sharedMemoryWorks`, `webgl2`,
`worker`, `workerAtomics`, `moduleWorker`, `wasm`, `wasmSimd`, plus the COOP/COEP header values.

---

## 4. Measured results

All checks pass on both transports, in every run.

| Measurement | `camxora-vizzy://` | loopback `http://127.0.0.1` |
|---|---|---|
| `crossOriginIsolated` | **true** | **true** |
| `isSecureContext` | true | true |
| COOP / COEP / CORP delivered | `same-origin` / `require-corp` / `cross-origin` | same |
| `SharedArrayBuffer` | `function` | `function` |
| page ↔ worker shared memory | `42` / `7` read back | `42` / `7` read back |
| WebGL2 | ok, real draw `[64,127,191,255]` | ok, real draw `[64,127,191,255]` |
| Classic worker | ok, isolated inside worker | ok, isolated inside worker |
| Module worker | ok, isolated inside worker | ok, isolated inside worker |
| WebAssembly validate / instantiate | `true` / `add(1,2)=3` | `true` / `add(1,2)=3` |
| WebAssembly SIMD (`v128`) | `true` | `true` |

Timing, window creation → probe complete (includes Playwright launch, Chromium warm-up and a
fresh profile each run):

| Run | Mode | Elapsed |
|---|---|---|
| `--mode=protocol` alone | protocol | 629 ms |
| `--mode=loopback` alone | loopback | 567 ms |
| both, protocol first | protocol / loopback | 1285 ms / 553 ms |
| first run in a cold checkout (AV + first GPU init) | protocol | ~5.7 s |

Timing is dominated by Electron/Chromium startup, not the transport; the transport
difference is below measurement noise (~60 ms). Do not treat this as a transport benchmark.

Probe paths observed inside the workers:

```
camxora-vizzy://vizzy/worker.js
camxora-vizzy://vizzy/worker-module.mjs
http://127.0.0.1:55449/t/<token>/worker.js
http://127.0.0.1:55449/t/<token>/worker-module.mjs
```

---

## 5. Recommendation: custom protocol primary, loopback fallback

**Primary:** `camxora-vizzy://vizzy/…` via `protocol.registerSchemesAsPrivileged` +
`protocol.handle`.

Reasons, in order of weight:

1. **Stable origin.** The origin is `camxora-vizzy://vizzy`, fixed for the life of the app.
   A loopback server on an ephemeral port produces a new origin (`http://127.0.0.1:<port>`)
   on every launch, so `localStorage`, `IndexedDB`, Cache Storage and service-worker scopes
   are discarded each run. Rea stores user presets and editor state in `localStorage`; losing
   it on every launch is a behaviour change. A fixed port would restore the origin but
   introduces port-collision and “port already in use” failure modes.
2. **No listening socket.** No port, no token lifecycle, no localhost listener for endpoint
   security agents or firewalls to flag, and nothing to leak if another local process scans
   loopback ports.
3. **No token plumbing.** Every asset URL would otherwise need the token prefix, which puts a
   secret in CSS `url()`, worker URLs, `new URL(..., import.meta.url)` and saved project
   references. The protocol has no such coupling.
4. **Verified parity.** Isolation, workers, WASM/SIMD and WebGL2 all behave exactly as on
   `http:` in this environment.

**Fallback:** the tokenised loopback server, already implemented and tested, behind one
transport switch. Trigger it if a future Electron/Chromium release stops honouring
COOP/COEP on custom schemes, or if the real bundle exposes a custom-scheme gap the minimal
page does not (for example a media/`Range` path).

**Guard:** `scripts/vizzy-host-spike.mjs` is the regression test for that decision — run it
in CI on the pinned Electron version. If `crossOriginIsolated` ever drops to false on the
protocol transport, the fallback exists and is known-good.

### 5.1 Conditions the real host must keep

- Register the scheme before `app.whenReady()`; install the handler after it.
- Serve **every** response (HTML, JS, CSS, fonts, WASM, errors, 404s) with all three headers.
- Send `text/javascript` for `.js`/`.mjs`, `application/wasm` for `.wasm`, and a real charset
  for text — module workers and `WebAssembly.instantiateStreaming` fail on wrong MIME.
- Stream assets and support `HEAD`/`Range` for video; the spike reads files synchronously,
  which is fine for a 20 KB page and not fine for a 265 MB asset pack.
- Keep `base: './'` in the Vizzy Vite build; absolute `/assets/…` paths still work because the
  scheme is `standard`, but relative base is what the custom scheme was tested with.
- Service workers are unavailable/undesirable on this scheme — keep Rea's service worker
  disabled as already planned in `02-MODULE-MAP.md` §3.8.
- CSP needs `'wasm-unsafe-eval'` for WebAssembly. Keep `'unsafe-eval'` out unless the port
  proves the formula evaluator needs `eval`; if it does, scope the relaxation to the Vizzy
  origin only.

---

## 6. Limitations and risks

| Risk | Status / mitigation |
|---|---|
| One machine, one GPU. macOS Metal and Linux Mesa were not measured. | Re-run the spike on each release platform; it is machine-checkable and ~1 s warm. |
| Minimal page, not the editor. No three.js, CanvasKit/Skia, Butterchurn, ffmpeg.wasm, 91 templates, video decode or 265 MB assets. | This proves the platform primitives, not the port. VZ-H1/VZ-H2 still need to run against the real bundle. |
| COOP/COEP on a non-`http(s)` scheme is not a web standard; Chromium could change it. | Measured working on Electron 45/Chromium 156 with the documented privileges. The loopback fallback is implemented, tested and one flag away. Script acts as the canary. |
| `require-corp` blocks every cross-origin subresource without CORP or CORS. Remote marketplace/template media, remote fonts or `http(s)` API images embedded in the canvas will fail. | Route remote media through `camxora-media://` (already sends no CORP today — **add `Cross-Origin-Resource-Policy: cross-origin` to `services/media.ts`** before the port) or proxy through the host. |
| Range requests / seeking for `<video>` over the protocol are unproven. | Add `Range` handling to the protocol handler and extend the spike with a video fixture before VZ-60 lands. |
| `protocol.handle` is synchronous file I/O in the spike. | Production handler must stream (`fs.createReadStream`) and cache immutable hashed assets. |
| A single privileged-scheme registration per process; double registration warns. | Register once at module scope in main, like `registerMediaScheme()`. |
| Origin is opaque to some tooling (`document.referrer`, DevTools network labels, `localStorage` inspection). | Acceptable for a hosted editor view; log the transport in diagnostics. |
| Blob workers were deliberately avoided; if Rea ever builds a worker from a Blob, COEP treats it as same-origin and it works, but that path is untested here. | Keep worker files as real assets. |
| CORS/`fetch` of `camxora-vizzy://` URLs from the shell origin will be cross-origin. | The shell must not fetch Vizzy assets; it talks to the view over the bridge only. |
| `protocol.handle` responses bypass some Electron session hooks (e.g. proxy, cache). | Fine for local assets; do not use the scheme for network content. |

---

## 7. Bridge skeleton (design only, not wired)

`electron/vizzy-host/bridge.ts` defines the contract from `02-MODULE-MAP.md` §3.1/§4.3 and a
router that is ready to be connected later:

```
view preload  --ipcRenderer.send("vizzy:bridge", msg)-->  ipcMain
ipcMain       --bridge.handleViewMessage(msg)--------->   handlers
bridge        --webContents.send("vizzy:bridge", msg)-->  view preload
view preload  ------------------------------------------>  window.camxoraVizzy
```

| Direction | Messages |
|---|---|
| view → host | `ready`, `dirty`, `save` (`ArrayBuffer`), `open`, `pick-media`, `export`, `cancel-export`, `log`, `error` |
| host → view | `init` (tokens + app + project), `theme`, `open-project`, `project-saved`, `media-picked`, `export-progress`, `export-done`, `export-failed`, `error` |

Every message carries `v: 1`. Binary payloads are `ArrayBuffer`, never base64. Handlers are
injected (`saveProject`, `openProject`, `pickMedia`, `startExport`, `cancelExport`,
`appInfo`, `log`), so the real implementation can reuse the existing project store, native
dialogs, `createMediaUrl()` and the FFmpeg service without this module importing them.

Deliberately **not** done here: no preload, no `ipcMain` registration, no import from
`electron/ipc/index.ts`, no shell wiring. The skeleton compiles under the repo's strict
TypeScript settings and is covered by the normal typecheck.

---

## 8. Reproduce

From the repository root:

```powershell
cd desktop-electron
npm ci
npm run typecheck
npm run lint
npm test
npm run build

# both transports, JSON report on stdout and in artifacts/
node scripts/vizzy-host-spike.mjs --out=artifacts/vizzy-host-spike/report.json

# one transport
node scripts/vizzy-host-spike.mjs --mode=protocol
node scripts/vizzy-host-spike.mjs --mode=loopback
```

Exit code is `0` only when every required check passes for every requested mode; failures are
listed under `failures` in the JSON and printed to stderr.

Direct launch without Playwright (useful when investigating a Chromium flag):

```powershell
cd desktop-electron
$env:VIZZY_SPIKE_MODE="protocol"                  # or "loopback"
$env:VIZZY_SPIKE_PAGE_ROOT=(Resolve-Path "electron/vizzy-host/page").Path
$env:VIZZY_SPIKE_EXIT_ON_DONE="1"
$env:VIZZY_SPIKE_USER_DATA="$env:TEMP\camxora-vizzy-host-spike\direct"
npx electron dist-electron/vizzy-host-spike/spike-main.cjs
```

The last stdout line is `VIZZY_SPIKE_RESULT <json>`; the bundled file is produced by the
runner above. Remove the `VIZZY_SPIKE_*` variables afterwards.

---

## 9. Files

| Path | Purpose |
|---|---|
| `electron/vizzy-host/assets.ts` | scheme constants, isolation headers, CSP, MIME map, path-traversal-safe asset resolver, `Response` builders (no Electron import) |
| `electron/vizzy-host/protocol.ts` | privileged scheme registration + `protocol.handle` handler |
| `electron/vizzy-host/server.ts` | tokenised `127.0.0.1` fallback server (GET/HEAD, ephemeral port) |
| `electron/vizzy-host/view.ts` | `WebContentsView`/`BrowserWindow` host with crash + navigation guards, and the `executeJavaScript` result reader |
| `electron/vizzy-host/spike-main.ts` | standalone spike main (bundled on demand; not part of the app build) |
| `electron/vizzy-host/bridge.ts` | bridge contract + router skeleton (self-contained, unused) |
| `electron/vizzy-host/page/` | probe page: `index.html`, `spike.js`, `worker.js`, `worker-module.mjs` |
| `scripts/vizzy-host-spike.mjs` | runner: bundles the spike main, launches both transports, reports JSON, fails on regression |
| `tests/unit/vizzy-host.test.ts` | asset resolver, traversal rejection, header, and loopback token/405 tests |

Evidence from the verification run: `desktop-electron/artifacts/vizzy-host-spike/report.json`
(git-ignored).

---

## 10. What this unlocks for P7

- VZ-H1 (COOP/COEP + worker) and VZ-H2 (custom protocol + no CSP violations) are proven for
  the platform; they now need re-running against the real Vizzy bundle.
- The 91-template asset pack can be served from the same scheme; no per-asset token, no
  origin churn, no server to supervise.
- The `WebContentsView` + `executeJavaScript` measurement path works, so the parity harness
  (`03-PARITY-HARNESS.md` §5) can read `window.__vizzyTest` exactly as planned.
- The one open platform item is **media**: add CORP to `camxora-media://` and test `Range`
  seeking over the custom scheme before the media page (VZ-60) is scheduled.
