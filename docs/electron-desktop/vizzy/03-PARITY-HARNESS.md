# Vizzy — Parity Harness and Acceptance

> **Document ID:** CAMXORA-ED-VZ-03
> **Version:** 1.0.0
> **Status:** Draft
> **Source:** Rea parity tooling (`editor/scripts`, `docs/parity-report.md`,
> `docs/reference-provenance.md`)
> **Last updated:** 2026-11-19

The port must not change what the renderer draws. The harness proves that the Electron host
preserves Rea's measured parity and that project I/O/export round-trips.

---

## 1. Baselines

| Baseline | What it is | Where |
|---|---|---|
| **Rea parity table** | 87–91 template rows, mean pixel diff vs captured references | `G:\Developments\Rea\docs\parity-report.md` / `.json` |
| **Rea browser tests** | Playwright checks for shell, presets, import, export, timeline | `G:\Developments\Rea\editor\test-*.mjs` |
| **Editor screenshots** | Full-window captures at 1440×900 and 1920×1080 | Captured for this program |
| **Export fixtures** | 10 reference projects with expected duration/codec/audio | Captured for this program |

A row is only comparable to another row measured against the **same reference file**, with
the same state preference, replay step, median-of-N and classifier. Do not compare across
re-captures; start a new baseline (P0) and measure deltas from there.

---

## 2. Reference corpus for the port

The full Rea corpus is large (hundreds of MB). Ship a **test corpus** of 10 projects that
cover the risky systems:

| # | Project | Covers |
|---|---|---|
| 1 | A 2D spectrum project | Spectrum layers, presets, analyser bindings |
| 2 | A 3D particles project | Three.js scene, particles, camera |
| 3 | A text/lyrics project | Skia text, lyrics, fonts |
| 4 | A video/media project | Video decode, source in/out, audio |
| 5 | An effects-heavy project | Post-processing, shaders, blending |
| 6 | An automation-heavy project | Keyframes, math, audio impact, groups |
| 7 | A 3D model project | Model, lights, ground |
| 8 | A Butterchurn project | Audio-visualizer node |
| 9 | A Lottie/Skottie project | Vector animation |
| 10 | A community/template export | Import mapping fidelity |

Fixtures are stored outside the installer under `tests/fixtures/vizzy/` and referenced by
hash. If a fixture cannot be redistributed, generate an equivalent synthetic project and
record the difference.

---

## 3. Three levels of verification

### 3.1 Boot and structure (fast, every CI run)

- [ ] Vizzy view loads and reports `ready`.
- [ ] `crossOriginIsolated === true` (threaded FFT tier can engage).
- [ ] WebGL2 context is created; no shader compile errors.
- [ ] A fixture project opens; node/layer/effect/analyzer counts match the expected snapshot.
- [ ] The timeline renders and the playhead moves.
- [ ] No uncaught console errors in the first 10 s.

### 3.2 Visual parity (per PR and nightly)

- [ ] Render frames at the same playhead/protocol as the Rea baseline.
- [ ] Compare mean absolute difference, lit fraction and per-region diff.
- [ ] Store screenshots with the project hash, time, resolution and FFT tier.
- [ ] Threshold: **no regression** larger than the Rea row's recorded spread; a regression
      above 1.0 mean diff on a stable row fails the PR.
- [ ] UI screenshots of the editor shell at 1440×900: no unexpected layout shift.

### 3.3 Round-trip and export (per PR and release)

- [ ] Open → save → reopen: project JSON is semantically identical (ignoring ids/timestamps).
- [ ] Import a Vizzy export → save → reopen: node kinds and key values match.
- [ ] Export image: PNG dimensions and a hash of a static frame match the baseline.
- [ ] Export video: playable container, expected codec, duration ±1 frame, audio stream present.
- [ ] Cancel export: no partial file left behind; app remains responsive.
- [ ] Export at 720p and 1080p; preview resolution does not affect output.

---

## 4. Host-specific tests

| ID | Scenario | Assert |
|---|---|---|
| VZ-H1 | COOP/COEP | `crossOriginIsolated` true; worker loads |
| VZ-H2 | Custom protocol | Assets load; CSP has no violations |
| VZ-H3 | Media URL | Local image/video/audio renders; outside-root path rejected |
| VZ-H4 | Native picker | Returns a path; cancel returns null; no hang |
| VZ-H5 | Save | Atomic write; recent list updates; dirty false |
| VZ-H6 | Autosave | 2 s debounce; recovery file exists |
| VZ-H7 | Crash isolation | Kill the view; shell survives; reload restores autosave |
| VZ-H8 | Route change | View detaches; no orphan process; audio stops |
| VZ-H9 | Window resize | Stage and timeline reflow; no canvas blur |
| VZ-H10 | Native export | Progress, cancel, output validation |
| VZ-H11 | Fonts | Bundled fonts load; no network request |
| VZ-H12 | Offline | Editor opens a local project without the network |

---

## 5. Test harness design

```
tests/e2e/vizzy/
  boot.spec.ts          # boot, isolation, WebGL
  project.spec.ts       # open/save/reopen/recent
  import.spec.ts        # Vizzy export import
  media.spec.ts         # picker + protocol
  export.spec.ts        # image/video/cancel
  crash.spec.ts         # view crash isolation
  visual.spec.ts        # screenshot diff
  fixtures/             # 10 projects + expected snapshots
```

Playwright launches Electron with a fixed window size, a temporary `userData` dir and a
fixture project path. It reads `window.__vizzyTest` through `webContents.executeJavaScript`.

### 5.1 Visual diff implementation

1. Reuse Rea's capture protocol: fixed playhead, warm analyser, same resolution, same
   device scale.
2. Screenshot only the stage canvas for renderer parity; screenshot the shell separately.
3. Compute mean absolute difference per channel and a lit-fraction mask.
4. Emit a JSON row per project/frame and a PNG diff for failures.
5. Compare against the Rea baseline row; fail on regression beyond the recorded spread.

Do not "fix" a template export to make a diff disappear. Every renderer change needs a
module quote from the Rea source and a baseline update.

---

## 6. Release evidence

For every release candidate, attach:

- the harness run id and machine/GPU;
- the 10-project matrix (boot, round-trip, export);
- the visual diff summary;
- the export probe output (`ffprobe -show_streams`);
- any known deviations with an owner and a follow-up task.

---

## 7. Non-goals

- Achieving 100 % parity with vizzy.io. The port preserves Rea's measured parity; improving
  it is a separate renderer program.
- Pixel-perfect parity between the Electron shell UI and the PySide6 app. The shell is a
  design refresh.
- Testing every one of the 87 template rows on every PR. Run the full corpus nightly and the
  10-project set per PR.
