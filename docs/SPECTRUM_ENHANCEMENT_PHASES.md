# Spectrum enhancement phases (plan — not implemented)

**Date:** 2026-07-29  
**Status:** documented only — **do not implement until explicitly kicked off**  
**Architecture rule:** keep Spectrum / Particles / Logo domains separate. Couple only via small shared DTOs (e.g. logo bounds for attach).

Related parked code (already done, separate branch):

- Branch: `fix/spectrum-layer-ui-and-colors`
- Worktree: `MusicGenerator-spectrum`
- Commit: multi-stop gradient preview parity, layer Up/Down, curved rabbit-ears gravity
- Changelogs: `docs/changelog/2026-07-29-spectrum-multi-stop-gradient-preview.md`, `docs/changelog/2026-07-29-spectrum-layer-reorder-and-rabbit-ears.md`

This document plans **new** Spectrum (and one Particles) capabilities needed to match reference looks. It is the source of truth before coding.

---

## Goals

Unlock poster-style spectrum looks without rewriting the visualizer architecture:

1. Classic circular needles / capsules / ribbons / rainbow (mostly possible today).
2. Floating peak caps, denser bars, real solid band / base ring, vertical bar gradients.
3. Contour / radio-wave style + reflection.
4. Spectrum path following square logo edges.
5. Particle motion trails (Particles domain only).

---

## Already available (settings / existing code)

| Capability | How |
|------------|-----|
| Multi-stop rainbow (≤5) | Spectrum color engine + layer UI (preview/export parity fixed) |
| Horizontal ribbon | `curved: false` + gravity |
| Circular / semicircle ring | `curved` + `mirrored` |
| Presets | `orbit-spikes`, `signal-needles`, `pulse-beads`, `aurora-ribbon`, `magma-ridge`, `drift-capsules`, … |
| Layers + reorder | Layer editor Up/Down |
| Logo square vs circle crop | Logo `circleMask` (spectrum attach still circular) |
| Particle styles + travel | Particles inspector (no trails yet) |

---

## Capability gaps vs references

| Gap | Domain | Notes |
|-----|--------|-------|
| Floating peak caps | Spectrum | `audioPeakHoldBlend` exists; caps not drawn |
| Bar count / density | Spectrum | ~fixed bin count today |
| Solid base ring stroke | Spectrum | Missing polish under bars |
| Wire `solidBand` for real | Spectrum | UI exists; GPU path incomplete |
| Vertical gradient along bar height | Spectrum | Color is bar-index today |
| Honor `gradientDirection` in paint | Spectrum | Stored; mostly unused in vertex colors |
| Contour / multi-line wave style | Spectrum | New style (large) |
| Spectrum mirror / reflection | Spectrum | Medium |
| `pathMode: circle \| rect` | Spectrum (+ logo bounds DTO) | Attach is circle radius only |
| Particle motion trails | Particles | No history / trail GPU path |

---

## Phase plan

### Phase 0 — already landed (parked branch)

- Multi-stop gradient preview = export
- Layer reorder UI + clearer labels
- Curved bottom / rabbit-ears gravity direction

**Ship gate:** only when product asks to merge `fix/spectrum-layer-ui-and-colors`. Not part of desktop 1.0.1 consolidation.

### Phase 1 — unlock most poster looks (Spectrum only)

**Priority:** highest visual jump for circular / linear poster refs.

| Item | Acceptance |
|------|------------|
| Peak caps | Optional floating tops with color / gap / decay; preview + export |
| Bar density | User-visible bar count (or density) control; clamped for GPU cost |
| Real `solidBand` / base ring | Continuous band or stroke under/around bars when enabled |
| Vertical bar gradient | Color can vary along bar height (in addition to along ring) |

**Out of scope for Phase 1:** contour waves, square path, particle trails.

**Likely touch points (when implementing):**

- `features/video/widgets/spectrum_layer_editor.py` / `spectrum_inspector.py`
- `features/video/lib/spectrum_color_engine.py`, `spectrum_style_registry.py`, draft/save normalizers
- `visualizer/_spectrum_fast.py`, `preview_widget.py`, `gpu_render.py`
- Tests for color + geometry; changelog under `docs/changelog/`

### Phase 2 — special styles (Spectrum)

| Item | Acceptance |
|------|------------|
| Contour / radio-wave preset | Multi-line outlined wave rings (new style id) |
| Reflection / mirror of spectrum | Optional mirrored copy (e.g. floor reflection) |

**Depends on:** Phase 1 density/solid band helpful but not strictly required for reflection scaffolding.

### Phase 3 — shape follow (Spectrum + thin Logo DTO)

| Item | Acceptance |
|------|------------|
| `pathMode: circle \| rect` | When attach-on + logo square, bars follow rect perimeter |
| Logo bounds DTO | Logo publishes `{ center, halfW, halfH, shape, … }`; Spectrum consumes only that |

**Do not:** import logo PNG alpha into spectrum-only modules; no silhouette SDF in Phase 3.

### Phase 4 — particle trails (Particles only)

| Item | Acceptance |
|------|------------|
| Trail settings | `trailEnabled`, length, opacity, fade in `particlesSettings` |
| Sim + GPU | History buffer or trail samples; faded quads/ribbons |
| Inspector | Particles UI controls only |

**Do not:** hang trails off spectrum bar positions unless a later product brief requires a shared runtime DTO.

---

## Explicit non-goals (for these phases)

- Mixing Particles into Spectrum inspector or vice versa
- One mega “effect pack” that owns logo + spectrum + particles
- Shipping spectrum phases inside desktop **1.0.1** consolidated installer
- Arbitrary logo silhouette path (post–Phase 3 research)

---

## Suggested implementation order (when kicked off)

1. New branch / worktree from agreed base (prefer extend `fix/spectrum-layer-ui-and-colors` or cut fresh from `main` after Phase 0 merges).
2. Phase 1 only → tests + `docs/changelog/YYYY-MM-DD-spectrum-phase1-….md` + root `CHANGELOG.md`.
3. Sandbox desktop build only if product wants to trial; no production publish without ask.
4. Then Phase 2 / 3 / 4 as separate PRs.

---

## Decision log

| Date | Decision |
|------|----------|
| 2026-07-29 | Plan written; **no implementation** until user kicks off |
| 2026-07-29 | Phase 1 kicked off and implemented on `fix/spectrum-layer-ui-and-colors` |
| 2026-07-29 | Public desktop stays **1.0.1** consolidated; spectrum stays on parked branch |
| 2026-07-29 | Domains stay split; rect-follow uses logo bounds DTO |

---

## Open questions (resolve at kickoff)

1. Default bar density for existing templates (preserve look vs denser default)?
2. Peak caps on by default for which presets?
3. Should `solidBand` replace wide-bar approximation or sit beside it?
4. Phase 3 rect path: sharp corners vs rounded-rect?
5. Trails (Phase 4) before or after Phase 3?
