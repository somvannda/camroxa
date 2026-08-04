# Preview Compositing & Interactivity Requirements

> **Document ID:** CAMXORA-PREVIEW-COMPOSITE-INTERACT  
> **Version:** 1.0.0  
> **Status:** Approved for implementation — execute **priority order** (P0 → P4)  
> **Scope:** Desktop `camxora_python` only (Video live preview + window chrome touchpoints)  
> **Out of scope:** Qt RHI / Vulkan rewrite, playlist glass feature port, DistroKid, production deploy  
> **Related:**  
> - [`camxora_python/.docs/pages/09_VIDEO_REQUIREMENTS.md`](../camxora_python/.docs/pages/09_VIDEO_REQUIREMENTS.md)  
> - [`camxora_python/.docs/pages/09_VIDEO_ELECTRON_PYTHON_APP_INTEGRATION.md`](../camxora_python/.docs/pages/09_VIDEO_ELECTRON_PYTHON_APP_INTEGRATION.md)  
> - [`docs/changelog/2026-07-30-playlist-phase1.md`](changelog/2026-07-30-playlist-phase1.md) (see-through note)  
> - [`docs/changelog/2026-08-04-desktop-1.0.19-ship-cut.md`](changelog/2026-08-04-desktop-1.0.19-ship-cut.md) (why blend call-site fix was lost)  
> - [`docs/changelog/2026-08-04-preview-opaque-alpha-p0.md`](changelog/2026-08-04-preview-opaque-alpha-p0.md) (**P0 implementation**)  
> - [`docs/changelog/2026-08-04-preview-p1-diag-failure-ux.md`](changelog/2026-08-04-preview-p1-diag-failure-ux.md) (**P1 implementation**)  
> - [`docs/changelog/2026-08-04-preview-p2-interactive-perf.md`](changelog/2026-08-04-preview-p2-interactive-perf.md) (**P2 implementation**)  
> - [`docs/changelog/2026-08-04-preview-p3-chrome-audit.md`](changelog/2026-08-04-preview-p3-chrome-audit.md) (**P3 audit**)  
> - [`docs/GPU_EXPORT_PERFORMANCE_REQUIREMENTS.md`](GPU_EXPORT_PERFORMANCE_REQUIREMENTS.md)  
> **Last updated:** 2026-08-04

---

## 1. Purpose

Users on some GPUs (confirmed reports: AMD Ryzen 7 6800U iGPU class, NVIDIA RTX 2070 Super) open the Video page and see **through the live preview to the desktop / windows behind CAMXORA**. The developer cannot always reproduce locally because the failure depends on **OpenGL FBO alpha × Qt translucent frameless window × driver compositing**.

Separately, adjusting Video inspector controls while the live preview runs often feels **laggy**. That is primarily an **update-pipeline / main-thread** problem, not proof that OpenGL must be replaced.

This document defines **what must be delivered** for:

| Priority | Theme | User outcome |
|----------|--------|----------------|
| **P0** | Preview opaque compositing | Preview never punches desktop holes |
| **P1** | Diagnostics & failure UX | Support can prove GL health; failures are visible, not transparent |
| **P2** | Interactive settings performance | Sliders feel responsive with live preview |
| **P3** | Window chrome compositing | Translucent chrome does not amplify alpha holes |
| **P4** | Visual quality (HDR / bloom) | Glow/shine quality without leaving ModernGL |

**There is no P5 in this program.** Qt RHI / Vulkan / offscreen-blit architecture migration is explicitly deferred and must not be started under this document.

---

## 2. How to use this document (anti-drift rules)

Agents and implementers often deliver “related work” that misses the actual requirement. These rules are mandatory:

1. **One REQ at a time** unless the REQ explicitly allows a bundle (e.g. P0-BUNDLE).
2. **Read the Code anchors** before editing. If the anchor code no longer exists, **stop and update this document** — do not invent a parallel path.
3. **Out of scope is rejectable.** If a PR/diff includes playlist glass, DistroKid, RHI, Vulkan, Electron, or admin portal, it **fails** this program even if preview “also improved.”
4. **Acceptance Criteria are the contract.** Visual preference (“looks nicer”) is not acceptance unless a criterion says so with a measurable check.
5. **Definition of Done** at the end of each REQ must all be true before marking the REQ complete.
6. **Do not bury safety fixes inside feature ports.** P0 call-site fixes must be standalone commits/PRs so ship cuts cannot wipe them again (lesson from `1a68a91` reverting `856140e`).
7. **Preserve architecture boundaries** in §4. Do not move preview rendering into Electron, React, or a new process unless a future document says so.

### Requirement language

| Word | Meaning |
|------|---------|
| **SHALL** | Mandatory. Delivery fails without it. |
| **SHALL NOT** | Forbidden. Delivery fails if present. |
| **SHOULD** | Strongly preferred; justify in changelog if skipped. |
| **MAY** | Optional. |

---

## 3. Problem analysis (codebase-backed)

### 3.1 See-through preview (P0 / P3)

| Fact | Location |
|------|----------|
| Live preview is `QOpenGLWidget` + ModernGL | `camxora_python/visualizer/preview_widget.py` → `VideoSpectrumPreview` |
| Root window is frameless + **`WA_TranslucentBackground`** | `camxora_python/shared/lib/window_chrome.py` → `configure_rounded_window` |
| `QMainWindow` background is transparent; opaque shell is `#window_surface` | `camxora_python/shared/themes/deep_blue.py` |
| Alpha-preserving helpers exist | `VideoSpectrumPreview._blend_normal` / `_blend_additive` (RGB blend + alpha `ZERO, ONE`) |
| Spectrum glow still overwrites with 2-arg blends | ~~`preview_widget.py` ~2245–2250~~ **fixed in P0** (`_blend_additive` / `_blend_normal`) |
| Particles overwrite blends | ~~`gpu_render.py`~~ **fixed in P0** (`blend_rgb_*_opaque_alpha`) |
| Lightning overwrite blends | ~~`lightning_render.py`~~ **fixed in P0** |
| A correct call-site patch existed inside playlist port `856140e`, then was **lost** in ship-cut revert `1a68a91` | See `docs/changelog/2026-08-04-desktop-1.0.19-ship-cut.md` |

**P3 audit (2026-08-04):** Keep `WA_TranslucentBackground` for rounded frameless chrome. Opaque backplate remains `#window_surface`. See-through is addressed by P0 Alpha_Lock, not by removing translucency. Full write-up: [`docs/changelog/2026-08-04-preview-p3-chrome-audit.md`](changelog/2026-08-04-preview-p3-chrome-audit.md). P3.2 (opaque HWND / DWM-only corners) deferred until a post-P0 GPU reproduction exists.

**Mechanism:** Soft glow / additive / translucent draws write **framebuffer alpha &lt; 1**. On a translucent top-level HWND, Qt/Windows treat that alpha as **real window transparency** → desktop shows through the preview.

**Not the cause:** Missing app background panel. `#window_surface` is opaque. Custom title bar painting transparent is normal; it sits on the opaque surface. The hole is the **GL FBO alpha path**, not “no chrome fill.”

### 3.2 Slow inspector ↔ preview (P2)

| Fact | Location |
|------|----------|
| Draft changes schedule preview ~48ms | `video_view.py` → `_preview_update_timer` / `_schedule_preview_update` |
| Flush calls full preview update / normalizer path | `video_view.py` → `_flush_preview_update` → `_update_preview` → `TemplateNormalizer.to_renderer_dict` |
| `set_template` re-normalizes and fingerprints via **full `json.dumps`** | `preview_widget.py` → `set_template` (comment: normalize is expensive) |
| Peak cache cleared on every accepted template push | `set_template` → `_spectrum_peak_cache.clear()` |
| Preview paints on a 60 FPS timer | `VideoSpectrumPreview.__init__` → `timer.start(1000 // 60)` |
| Hitch breadcrumb when `paintGL` ≥ 40ms | `paintGL` finally block |

**Mechanism:** Main-thread Python rebuild + heavy paint contending with slider events. **Not** evidence that OpenGL must be replaced by RHI/Vulkan for snappy controls.

### 3.3 Visual “cheap glow” (P4)

Glow today is largely **extra soft-alpha / additive geometry** into an SDR-ish RGBA target, not an HDR float target + thresholded bloom + tonemap. OpenGL can do HDR; the current pipeline mostly does not.

---

## 4. Architecture constraints (non-negotiable)

| Constraint | Requirement |
|------------|-------------|
| Stack | Keep **PySide6 + `QOpenGLWidget` + ModernGL** for live preview under this program |
| Preview module | `camxora_python/visualizer/preview_widget.py` remains the live preview surface |
| Shared GPU helpers | Prefer shared helpers in `visualizer/gpu_render.py` and `features/video/lib/*_render.py` so preview/export stay aligned where they already share code |
| UI | Video inspectors stay PySide6 + `shared/themes/deep_blue.py`; no new design system |
| Template contract | Do not change template JSON schema unless a P4 REQ explicitly requires a new optional field with backward-compatible defaults |
| Branch / ship | One task → one branch; commit/push/prod only on explicit ask; sandbox-first if deploying |
| Playlist / DistroKid | **SHALL NOT** be reintroduced by this program |
| Backend migration | **SHALL NOT** introduce Qt RHI, Vulkan, Metal, or Electron preview under this program |

```
┌─────────────────────────────────────────────────────────────┐
│ RootWindow (frameless)                                      │
│  WA_TranslucentBackground + mask (rounded chrome)           │
│  ┌─ QWidget#window_surface (opaque #0f1923) ─────────────┐  │
│  │ title bar │ AppShell → VideoView                      │  │
│  │           │  StagePanel → AspectRatioBox             │  │
│  │           │    VideoSpectrumPreview (QOpenGLWidget)   │  │
│  │           │      ModernGL → Qt FBO (RGBA)             │  │
│  └───────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
```

---

## 5. Glossary

| Term | Meaning |
|------|---------|
| **Preview_FBO** | Qt `QOpenGLWidget` default framebuffer used each `paintGL` |
| **Alpha_Lock** | `blend_func` with RGB factors for look + alpha factors `(ZERO, ONE)` so destination alpha stays 1 after `clear(..., 1)` |
| **See_Through** | User-visible desktop/apps behind CAMXORA through the preview rect (or whole window) |
| **Call_Site_Patch** | Replacing raw `ADDITIVE_BLENDING` / 2-tuple blends at draw sites with `_blend_additive` / `_blend_normal` (or shared equivalent) |
| **Interactive_Scrub** | User is actively dragging a slider/spin/color control |
| **Full_Template_Push** | `normalize_renderer_template` / `to_renderer_dict` + `set_template` of an entire template dict |
| **HDR_Intermediate** | Float render target (e.g. `RGBA16F`) before tonemap to 8-bit display/encode |

---

## 6. Priority index

| ID | Priority | Title | Depends on |
|----|----------|-------|------------|
| REQ-P0.1 | P0 | Spectrum Call_Site_Patch | — |
| REQ-P0.2 | P0 | Particle Alpha_Lock | REQ-P0.1 helpers exist |
| REQ-P0.3 | P0 | Lightning Alpha_Lock | REQ-P0.1 helpers exist |
| REQ-P0.4 | P0 | End-of-frame opaque alpha harden | REQ-P0.1 |
| REQ-P0.5 | P0 | Manual GPU verification matrix | REQ-P0.1–P0.4 |
| REQ-P0.6 | P0 | Hotfix packaging / changelog | REQ-P0.1–P0.5 |
| REQ-P1.1 | P1 | Preview GL diagnostics on release line | — |
| REQ-P1.2 | P1 | initializeGL failure opaque fallback | — |
| REQ-P1.3 | P1 | FBO bind failure safety | — |
| REQ-P1.4 | P1 | Regression checklist + support pack | REQ-P0.6, REQ-P1.1 |
| REQ-P2.1 | P2 | Profile interactive path (baseline) | — |
| REQ-P2.2 | P2 | Incremental preview field updates | REQ-P2.1 |
| REQ-P2.3 | P2 | Cheap dirty detection | REQ-P2.2 |
| REQ-P2.4 | P2 | Cache retention on minor tweaks | REQ-P2.2 |
| REQ-P2.5 | P2 | Scrub-time preview rate limiting | REQ-P2.1 |
| REQ-P2.6 | P2 | Interactive reduced-effect mode | REQ-P2.5 |
| REQ-P3.1 | P3 | Translucent chrome audit | REQ-P0 done |
| REQ-P3.2 | P3 | Safer rounded-window strategy (if needed) | REQ-P3.1 |
| REQ-P4.1 | P4 | HDR intermediate design spike | P0–P2 stable |
| REQ-P4.2 | P4 | Real bloom + tonemap (preview) | REQ-P4.1 |
| REQ-P4.3 | P4 | Preview/export parity for bloom path | REQ-P4.2 |

---

# P0 — Opaque preview compositing

**Goal:** On affected GPUs, with frameless translucent chrome, the preview rect **SHALL** remain fully opaque to the desktop while glow/particles/lightning still look correct.

**Global P0 SHALL NOT:**

- Re-apply playlist glass / `playlist_glass_backdrop` / playlist Looks polish from `856140e`.
- Change spectrum Save / Row Width / other unrelated video features.
- “Fix” see-through by painting a black `QLabel` over the GL widget as the permanent solution (allowed only as temporary `initializeGL` failure fallback in P1).

---

## REQ-P0.1 — Spectrum Call_Site_Patch

### Problem

Helpers `_blend_normal` / `_blend_additive` exist, but spectrum glow/additive passes still assign raw blends and punch Preview_FBO alpha.

### Code anchors

- `camxora_python/visualizer/preview_widget.py`
  - Keep: `_blend_normal`, `_blend_additive`
  - Change: spectrum pass block that sets `moderngl.ADDITIVE_BLENDING` / 2-tuple blend (~lines 2245–2250 in current tree)
- Reference behavior: commit `856140e` **only** the three call-site lines that switched to `_blend_additive()` / `_blend_normal()` — **not** the rest of that commit

### Requirements

1. THE spectrum glow pass SHALL call `self._blend_additive()` instead of `moderngl.ADDITIVE_BLENDING`.
2. THE spectrum screen/add/lighten blend modes SHALL call `self._blend_additive()`.
3. THE spectrum normal blend path SHALL call `self._blend_normal()`.
4. THE implementation SHALL NOT modify playlist/text overlay glass sampling, overlay limit 64→256, frequency scroll, or other unrelated hunks from `856140e`.
5. After each spectrum pass group that temporarily changes blend, subsequent draws that expect normal blending SHALL restore Alpha_Lock via `_blend_normal()` where the existing paint order already does (logo/text) — do not remove those restores.

### Acceptance Criteria

| # | Criterion | How to verify |
|---|-----------|---------------|
| A1 | No `moderngl.ADDITIVE_BLENDING` assignment remains inside the spectrum pass loop in `paintGL` | `rg "ADDITIVE_BLENDING" preview_widget.py` shows none in spectrum block (particles may still until P0.2) |
| A2 | Glow templates still show soft glow (RGB), not hard cutout | Manual: enable spectrum glow &gt; 0 |
| A3 | With a translucent window, preview does not show desktop through glow regions on a machine that previously reproduced See_Through **or** on a synthetic alpha readout test if available | Manual GPU matrix REQ-P0.5 / optional unit around blend factor tuple |
| A4 | Diff is limited to preview blend call sites (+ tests/changelog for this REQ) | `git diff --stat` review |

### Definition of Done

- [ ] A1–A4 true  
- [ ] Changelog entry under `docs/changelog/` stating **call-site only**, playlist excluded  
- [ ] Suggested commit message focuses on opaque preview alpha, not playlist  

---

## REQ-P0.2 — Particle Alpha_Lock

### Code anchors

- `camxora_python/visualizer/gpu_render.py` → `_render_particle_styled_quads` (sets `ADDITIVE_BLENDING` / 2-tuple)
- Caller: `preview_widget.py` → `_draw_particle_batch`

### Requirements

1. WHEN particles draw with glow/additive look, THE particle path SHALL use Alpha_Lock-equivalent blend (RGB additive or normal as today, alpha `ZERO, ONE`).
2. WHEN particles finish, THE blend state SHALL leave Alpha_Lock normal for subsequent logo/text draws (or preview shall re-assert `_blend_normal()` before logo — already present; keep it).
3. Export paths that share `_render_particle_styled_quads` SHALL keep correct RGB look; export offscreen FBO alpha MAY use the same Alpha_Lock (safe) and SHALL NOT regress export colors.

### Acceptance Criteria

| # | Criterion | Verify |
|---|-----------|--------|
| A1 | Particle glow no longer uses 2-channel-only blend that writes alpha down | Code review + `rg` |
| A2 | Music-note / neon particle styles still visible | Manual or existing `test_preview_particles.py` still pass |
| A3 | See_Through does not reappear when particles enabled + spectrum glow on | REQ-P0.5 |

### Definition of Done

- [ ] A1–A3  
- [ ] Existing particle tests pass  

---

## REQ-P0.3 — Lightning Alpha_Lock

### Code anchors

- `camxora_python/features/video/lib/lightning_render.py` (blend assignments ~219–221, restore ~291)
- Preview caller: `preview_widget.py` → `_finish_lightning_frame`

### Requirements

1. Lightning additive/normal blends SHALL use Alpha_Lock-equivalent factors when rendering into the Preview_FBO.
2. THE function SHALL accept either an explicit `opaque_framebuffer_alpha: bool = True` for preview, or unconditionally Alpha_Lock if export alpha is irrelevant — document choice in changelog.
3. Visual bolt color/glow intensity SHALL remain subjectively equivalent (no removing glow passes to “fix” alpha).

### Acceptance Criteria

| # | Criterion | Verify |
|---|-----------|--------|
| A1 | No preview lightning draw uses raw `ADDITIVE_BLENDING` without alpha lock | `rg` + review |
| A2 | Lightning still flashes/reacts with audio | Manual |
| A3 | Combined spectrum + lightning + particles stays opaque | REQ-P0.5 |

---

## REQ-P0.4 — End-of-frame opaque alpha harden

### Problem

Any future draw path that forgets Alpha_Lock can regress See_Through.

### Requirements

1. At the end of a successful `paintGL` (before returning), THE preview SHALL ensure Preview_FBO alpha is 1 for all pixels **or** for the full clear region used by the widget (implementation choice: colorMask + clear alpha only, or fullscreen opaque blit).
2. THE harden step SHALL NOT alter RGB content of the frame (no darkening/brightening).
3. THE harden step SHALL be skipped when `_export_overlay_active` early-returns before drawing (export freeze UI path) unless that path also exposes GL alpha — if skipped, document why.
4. THE harden step SHALL NOT call `grabFramebuffer()` (existing comment: stalls GPU).

### Acceptance Criteria

| # | Criterion | Verify |
|---|-----------|--------|
| A1 | Even if a test deliberately uses a leaking blend once, end-of-frame leaves opaque alpha | Prefer automated GL readback test if feasible; else code review + manual |
| A2 | No new hitch from harden alone (SHOULD keep added cost &lt; 1ms at 1080p-class preview size on mid GPU) | Hitch log / perf note |
| A3 | Still no `grabFramebuffer` in the hot path | `rg grabFramebuffer preview_widget.py` |

---

## REQ-P0.5 — Manual GPU verification matrix

### Requirements

1. Before claiming P0 complete, THE implementer SHALL run or obtain results for the matrix below (substitute GPUs allowed if documented).

| Case | Window | Template | Expected |
|------|--------|----------|----------|
| M1 | Windowed (rounded) | Spectrum glow high | Opaque preview; glow visible |
| M2 | Maximized | Same | Opaque |
| M3 | Windowed | Glow + particles + lightning | Opaque |
| M4 | Windowed | Glow off, particles off | Opaque dark/clear preview content |
| M5 | Windowed | Playlist/text overlays if present in template | Opaque (overlays may be translucent *within* the video image, but not to desktop) |

2. Results SHALL be recorded in the changelog or a short `docs/changelog/YYYY-MM-DD-preview-opaque-verification.md` with GPU/driver strings.

### Acceptance Criteria

- A1: M1–M5 recorded  
- A2: At least one NVIDIA and one AMD (or Intel) result SHOULD be included; if only one vendor available, state limitation explicitly  

---

## REQ-P0.6 — Hotfix scope & changelog

### Requirements

1. THE ship artifact for P0 SHALL include only P0-related desktop files (+ changelog + tests).
2. THE changelog SHALL state that playlist glass was **not** restored.
3. THE changelog SHALL reference the prior loss via 1.0.19 ship-cut revert so future ship cuts do not drop this again.

### Acceptance Criteria

- A1: `git diff` / PR file list contains no DistroKid / playlist glass feature files  
- A2: User-facing note: “fixes preview see-through on some GPUs”  

---

# P1 — Diagnostics & failure UX

## REQ-P1.1 — Preview GL diagnostics on release line

### Code anchors

- `camxora_python/visualizer/preview_diag.py`
- `camxora_python/tests/test_preview_gl_diag.py`
- Branch history: `bugfix/preview-gl-diag-logging` / commit `5516b88` (may not be on every release line)

### Requirements

1. Frozen installs SHALL append preview GL diagnostics to `%LOCALAPPDATA%\Camxora\logs\preview-gl-diag.log` (or current documented path from `preview_gl_diag_log_path`).
2. `initializeGL` success/failure, framebuffer id, and GL identity fields SHOULD be logged.
3. Diagnostics SHALL NOT spam every frame (rate-limit / milestone frames only).

### Acceptance Criteria

| # | Criterion | Verify |
|---|-----------|--------|
| A1 | Unit tests for diag path pass | `pytest camxora_python/tests/test_preview_gl_diag.py` |
| A2 | After launching Video page once, log file exists on Windows | Manual |
| A3 | Support doc snippet lists exact path | Changelog or REQ-P1.4 pack |

---

## REQ-P1.2 — initializeGL failure opaque fallback

### Requirements

1. WHEN `initializeGL` fails, THE stage SHALL show an **opaque** error panel (solid theme background + message), never an empty transparent GL hole.
2. THE user-visible message SHALL say GPU preview failed and point to logs if REQ-P1.1 is present.
3. Playback controls MAY disable; the rest of Video UI SHALL remain usable.

### Acceptance Criteria

- A1: Forced failure path (test double / inject) shows opaque fallback  
- A2: No desktop visible through preview host area  

---

## REQ-P1.3 — FBO bind failure safety

### Code anchors

- `preview_widget.py` → `_use_qt_framebuffer`

### Requirements

1. WHEN Qt FBO cannot be bound, `paintGL` SHALL skip drawing and leave a defined opaque clear **or** trigger the same fallback as REQ-P1.2 after N consecutive failures (document threshold).
2. SHALL NOT silently present uninitialized transparent pixels.

### Acceptance Criteria

- A1: Code path reviewed; no bare `return` after failed bind without opaque handling once P1 is done  
- A2: Log line written on bind failure  

---

## REQ-P1.4 — Regression checklist & support pack

### Requirements

1. THE support pack SHALL list: app version, `preview-gl-diag.log`, `camxora-*.log`, dxdiag display tabs, windowed vs maximized, template features enabled (glow/particles/lightning).
2. QA checklist SHALL include P0 matrix M1–M5.

### Acceptance Criteria

- A1: Checklist exists in changelog or `docs/` and is linked from this document’s related section on update  

---

# P2 — Interactive settings performance

**Goal:** While dragging common Video inspectors, UI stays responsive and preview tracks changes without full-template thrash.

**Global P2 SHALL NOT:**

- Replace OpenGL with RHI/Vulkan “for performance.”
- Remove live preview.
- Change export correctness to make scrubbing faster.

### Target metrics (measure in REQ-P2.1, enforce in later REQs)

Use a mid-tier machine; document GPU.

| Metric | Baseline (measure) | Target after P2 |
|--------|--------------------|-----------------|
| Main-thread work per slider tick during scrub | measured | SHOULD be &lt; 8ms median excluding paint |
| Full_Template_Push rate during continuous scrub | often every debounce | SHALL be ≤ 1 per scrub burst except on commit/release if incremental path used |
| `paintGL` hitch ≥ 40ms during scrub | measured count/min | SHOULD drop ≥ 50% vs baseline on same template |
| Perceived control lag | subjective | Slider thumb SHOULD NOT feel “stuck” for &gt; 100ms on typical spectrum opacity/glow sliders |

---

## REQ-P2.1 — Profile interactive path (baseline)

### Requirements

1. THE implementer SHALL measure and record where time goes for one spectrum slider drag: inspector handlers, `_schedule_preview_update`, `to_renderer_dict` / `normalize_renderer_template`, `set_template` fingerprint, `paintGL`.
2. Results SHALL be written to a changelog/perf note before implementing REQ-P2.2+.

### Acceptance Criteria

- A1: Written baseline with method (timestamps / existing hitch logs / cProfile)  
- A2: Top 2 cost centers identified  

---

## REQ-P2.2 — Incremental preview field updates

### Code anchors

- `video_view.py` → `_schedule_preview_update`, `_update_preview`, `TemplateNormalizer.to_renderer_dict`
- `preview_widget.py` → `set_template`

### Requirements

1. For a defined allowlist of high-churn numeric fields (at minimum: spectrum glow, opacity, bar width, particle opacity/size — list exact draft keys in the implementing changelog), Interactive_Scrub SHALL update preview via a **patch API** (e.g. `apply_preview_patch({...})`) that does **not** call full `normalize_renderer_template` every tick.
2. On scrub end / field commit / non-allowlisted fields, a Full_Template_Push SHALL still run to keep canonical state.
3. Preview drag offsets / edit modes already special-cased SHALL keep working.
4. THE allowlist SHALL be explicit; unknown fields fall back to full push (safe default).

### Acceptance Criteria

| # | Criterion | Verify |
|---|-----------|--------|
| A1 | Dragging an allowlisted slider does not call `normalize_renderer_template` every tick | Probe/log/counter in debug builds or unit test with mock |
| A2 | Releasing slider yields canonical template matching inspector values | Manual + optional assert |
| A3 | Non-allowlisted control still updates preview correctly via full push | Manual |
| A4 | No playlist/schema redesign |

### Definition of Done anti-patterns (reject)

- “We debounced to 200ms so it feels slower but cheaper” **without** incremental patch — fails A1 intent  
- Duplicating entire normalizer logic inside the widget with divergent semantics — fails architecture  

---

## REQ-P2.3 — Cheap dirty detection

### Requirements

1. `set_template` SHALL NOT require `json.dumps` of the entire template on every call once an incremental fingerprint/generation counter exists.
2. Identity/`is` short-circuit MAY remain.
3. Behavior SHALL NOT miss real changes (false negative dirty = forbidden).

### Acceptance Criteria

- A1: Hot path during scrub does not `json.dumps` full template every update  
- A2: Unit test: changing one field marks dirty; identical generation skips normalize  

---

## REQ-P2.4 — Cache retention on minor tweaks

### Requirements

1. `_spectrum_peak_cache.clear()` SHALL NOT run on every incremental patch that cannot affect peak geometry.
2. Cache SHALL clear when bar count, style preset, mirroring, or other geometry-affecting fields change (document rules).

### Acceptance Criteria

- A1: Opacity/glow-only patches do not clear peak cache  
- A2: Style preset change clears cache  
- A3: No stuck/incorrect peaks after style change  

---

## REQ-P2.5 — Scrub-time preview rate limiting

### Requirements

1. DURING Interactive_Scrub, preview repaint rate SHALL be capped (recommended 15–30 FPS) via timer adjustment or update coalescing.
2. WHEN scrub ends, preview SHALL return to normal ~60 FPS timer within 200ms.
3. Audio playback sync SHALL remain correct (clock not tied to the reduced paint rate incorrectly).

### Acceptance Criteria

- A1: Measurable lower `paintGL` frequency while dragging  
- A2: After release, frequency returns to normal  
- A3: No desync where displayed time freezes during playback scrub of visual params  

---

## REQ-P2.6 — Interactive reduced-effect mode

### Requirements

1. DURING Interactive_Scrub, preview MAY skip extra glow passes / reduce particle fill rate, then restore on scrub end.
2. If enabled, THE mode SHALL be automatic (no user setting required for v1) and SHALL NOT affect export.
3. Visual difference during scrub SHOULD be subtle; final frame after release SHALL match full quality.

### Acceptance Criteria

- A1: Export frames unchanged by this mode  
- A2: After scrub end, one full-quality frame is presented within 200ms  
- A3: Optional; if skipped, justify via REQ-P2.1 showing paintGL not in top costs  

---

# P3 — Window chrome compositing

## REQ-P3.1 — Translucent chrome audit

### Code anchors

- `shared/lib/window_chrome.py`
- `shared/themes/deep_blue.py` (`QMainWindow` transparent, `#window_surface` opaque)
- `shared/widgets/window_title_bar.py`

### Requirements

1. Document exactly why `WA_TranslucentBackground` is set and what breaks if cleared.
2. Confirm `#window_surface` remains the opaque backplate.
3. List any other `WA_TranslucentBackground` widgets that can overlap the preview host.

### Acceptance Criteria

- A1: Short audit section appended to changelog or this doc §3  
- A2: No code change required if audit says current approach is required **and** P0 holds on matrix  

---

## REQ-P3.2 — Safer rounded-window strategy (conditional)

### Requirements

1. ONLY IF REQ-P0 + REQ-P3.1 show translucency still causes vendor-specific holes despite Alpha_Lock, implement a safer approach (e.g. DWM corner preference + opaque window without per-pixel alpha, or mask-only).
2. Rounded appearance SHALL remain within 8px-class radius unless product says otherwise.
3. SHALL NOT remove frameless custom title bar unless product approves.

### Acceptance Criteria

- A1: Before/after screenshots of chrome  
- A2: P0 matrix still passes  
- A3: If not implemented, explicit “not needed after P0” note with evidence  

---

# P4 — Visual quality (ModernGL HDR / bloom)

**Gate:** Start only after P0 is shipped and P2 baseline exists (so quality work is not confused with jank).

## REQ-P4.1 — HDR intermediate design spike

### Requirements

1. Produce a short design (in `docs/` or changelog) specifying: float target format, tonemap, how Alpha_Lock interacts with HDR (window compositing still needs opaque alpha **after** tonemap into Qt FBO).
2. Spike MAY be a branch prototype behind a flag; SHALL NOT rewrite the whole visualizer.

### Acceptance Criteria

- A1: Written design with sequence diagram: scene → HDR → bloom → tonemap → opaque SDR FBO  
- A2: Explicit note: Qt window alpha remains 1 after tonemap  

---

## REQ-P4.2 — Real bloom + tonemap (preview)

### Requirements

1. Preview SHALL support a bloom path: threshold bright regions → blur pyramid → composite → tonemap to SDR for display.
2. Existing “fat soft-alpha glow strokes” MAY remain as a fallback or secondary; primary shine for high-glow settings SHOULD use bloom when flag enabled.
3. Default for existing templates SHALL remain backward compatible (no sudden over-bloom); enable via setting/flag with safe default.

### Acceptance Criteria

| # | Criterion | Verify |
|---|-----------|--------|
| A1 | HDR/bloom flag off → visual parity with pre-P4 | Side-by-side |
| A2 | Flag on → brighter bloom without desktop See_Through | Manual |
| A3 | Performance: paintGL SHOULD stay under 40ms median at preview size on mid GPU | Hitch logs |

---

## REQ-P4.3 — Preview/export parity

### Requirements

1. Export path SHALL use the same bloom/tonemap contract when the flag/setting is on so WYSIWYG holds.
2. Disabling the flag keeps prior export look.

### Acceptance Criteria

- A1: Same template + flag → preview frame vs export frame comparable (documented tolerance)  
- A2: Flag off → prior export golden behavior preserved  

---

# 7. Cross-cutting quality gates (every delivery)

Before merging any REQ in this program:

| Gate | Rule |
|------|------|
| G1 | Diff reviewed against **Out of scope** §1 / §2 |
| G2 | `pytest` for touched tests passes |
| G3 | No new `grabFramebuffer` in preview hot path |
| G4 | Changelog written (`docs/changelog/` + surface note if releasing) |
| G5 | Architecture boundaries §4 respected |
| G6 | If touching blends: Alpha_Lock preserved on preview FBO |
| G7 | Manual smoke: open Video page, play preview 10s, drag one slider |

---

## 8. Traceability — user complaints → REQs

| User / product signal | REQ |
|-----------------------|-----|
| “Preview see-through to desktop” on AMD/NVIDIA | P0.1–P0.6, P3.* |
| “Cannot reproduce locally” | P1.1, P1.4, P0.5 |
| “Settings / sliders lag with live preview” | P2.1–P2.6 |
| “Glow/colors look cheap vs other editors” | P4.1–P4.3 |
| “Just rewrite in Vulkan/RHI” | **Rejected by this document** (deferred; not P5 here) |
| “Bring back playlist glass with the blend fix” | **Rejected**; blend fix must be standalone (P0.1) |

---

## 9. Suggested implementation order (strict)

```
P0.1 → P0.2 → P0.3 → P0.4 → P0.5 → P0.6
        ↓
P1.1 → P1.2 → P1.3 → P1.4
        ↓
P2.1 → P2.2 → P2.3 → P2.4 → P2.5 → (P2.6 optional)
        ↓
P3.1 → (P3.2 conditional)
        ↓
P4.1 → P4.2 → P4.3
```

---

## 10. Document maintenance

When code anchors move, update §3 and the affected REQ **in the same PR** as the code change. Do not leave this document stale — stale anchors are how wrong implementations get shipped.
