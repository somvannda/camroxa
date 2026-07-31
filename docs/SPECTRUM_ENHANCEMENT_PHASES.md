# Spectrum enhancement phases

**Date:** 2026-07-29  
**Status:** Phase 0ΓÇô4 implemented on spectrum branch  
**Architecture rule:** keep Spectrum / Particles / Logo domains separate. Couple only via small shared DTOs (e.g. logo bounds for attach).

Related parked code:

- Branch: `fix/spectrum-vivid-position-audio` (continues earlier spectrum work)
- Worktree: `MusicGenerator-spectrum`

---

## Goals

1. Classic circular needles / capsules / ribbons / rainbow.
2. Peak caps, denser bars, solid band, vertical bar gradients.
3. Contour / radio-wave style + reflection.
4. Spectrum path following square logo edges.
5. Particle motion trails (Particles domain only).

---

## Already available

| Capability | How |
|------------|-----|
| Multi-stop rainbow (Γëñ5) | Spectrum color engine + layer UI |
| Circular / semicircle ring | Circle Form 180┬░ / 360┬░ |
| Presets | includes `contour-waves`, `orbit-spikes`, `aurora-ribbon`, ΓÇª |
| Peak caps / density / solidBand / vertical gradient | Phase 1 |
| Contour waves + floor reflection | Phase 2 |
| Directional bar growth | Top / Bottom / Left / Right |
| Path shape circle / rect | Phase 3 (`pathMode` + `LogoBounds`) |
| Particle motion trails | Phase 4 (`trailEnabled` + length/fade/width) |
| Radial bar spikes | Bar Growth **Outside** / **Inside** |

---

## Phase plan

### Phase 0ΓÇô1 ΓÇö landed

Multi-stop colors, layer reorder, directional growth, peak caps, density, solidBand, vertical gradients.

### Phase 2 ΓÇö landed

| Item | Status |
|------|--------|
| Contour / radio-wave preset (`contour-waves`) | done |
| Floor reflection (`reflectionEnabled` / `reflectionOpacity`) | done |

### Phase 3 ΓÇö landed

| Item | Status |
|------|--------|
| `pathMode: auto \| circle \| rect` | done |
| Logo bounds DTO | done (`LogoBounds`) |
| Attach + square logo ΓåÆ rect perimeter | done (Auto) |

### Phase 4 ΓÇö landed

| Item | Status |
|------|--------|
| Trail settings + sim history buffer | done |
| GPU styled-quad trail draw (preview + export) | done |
| Particles inspector controls | done |

---

## Decision log

| Date | Decision |
|------|----------|
| 2026-07-29 | Phase 1 implemented |
| 2026-07-29 | Phase 2 contour + reflection implemented |
| 2026-07-29 | Phase 3 rect path + LogoBounds; sharp corners (not rounded) |
| 2026-07-29 | Phase 4 particle trails; Particles-only; reuse head style with fade |

---

## Open questions

1. Remove Logo ΓÇ£Attach SpectrumΓÇ¥ toggle if ring already tracks logo size?
2. Fold trail fields into particle motion presets?
