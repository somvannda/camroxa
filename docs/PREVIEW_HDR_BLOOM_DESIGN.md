# Preview / export HDR intermediate + bloom (REQ-P4.1 design spike)

**Date:** 2026-08-04  
**Status:** design only — **no renderer rewrite in this commit**  
**Branch:** `docs/preview-p4-hdr-bloom-design`  
**Spec:** [`PREVIEW_COMPOSITING_AND_INTERACTIVITY_REQUIREMENTS.md`](../PREVIEW_COMPOSITING_AND_INTERACTIVITY_REQUIREMENTS.md) P4  
**Depends on:** P0 Alpha_Lock shipped (opaque Qt FBO alpha after display tonemap)

---

## 1. Problem

Today’s “glow” is mostly **extra soft-alpha / additive geometry** into an SDR-ish
RGBA8 Preview_FBO. Bright values clip at ~1.0, so shine looks cheap compared to
CapCut-class editors that bloom in a float intermediate.

OpenGL / ModernGL can already do `RGBA16F`. The limit is pipeline shape, not the API.

---

## 2. Target pipeline (preview + later export)

```
┌──────────────┐
│ Scene draw   │  spectrum / logo / particles / lightning / text
│ (linear HDR) │  write into float color attachments (values may be > 1)
└──────┬───────┘
       ▼
┌──────────────┐
│ HDR color    │  Texture / FBO: RGBA16F (scene)
│ buffer       │
└──────┬───────┘
       ▼
┌──────────────┐
│ Bloom        │  1) threshold bright (luma > T)
│ extract+blur │  2) downsample pyramid (e.g. 1/2 … 1/16)
│              │  3) upsample + additive composite into bloom buffer
└──────┬───────┘
       ▼
┌──────────────┐
│ Composite    │  HDR = scene + bloomStrength * bloom
└──────┬───────┘
       ▼
┌──────────────┐
│ Tonemap      │  e.g. ACES approx / Reinhard / exposure * curve → SDR RGB in 0..1
└──────┬───────┘
       ▼
┌──────────────┐
│ Qt Preview   │  Blit SDR RGB into QOpenGLWidget FBO
│ FBO (SDR)    │  **Alpha forced to 1.0** (P0 / P3: translucent HWND)
└──────────────┘
```

**Hard rule (A2):** After tonemap, the Qt composited Preview_FBO **SHALL** have
alpha = 1 everywhere. HDR/bloom work happens in **offscreen** float targets;
never leave bloom alpha in the window FBO.

Export (REQ-P4.3 later): same HDR→bloom→tonemap contract, then readback /
encode SDR (or 10-bit later). Flag off = today’s path for parity.

---

## 3. Formats & color

| Stage | Format | Notes |
|-------|--------|-------|
| Scene + bloom temps | `RGBA16F` | Prefer over `RGBA32F` for bandwidth |
| Display / Qt FBO | Default widget format (typically RGBA8) | Opaque alpha |
| Working space | Linear | Sample sRGB textures → linear; light/glow in linear; tonemap → sRGB encode for display |

Legacy soft-alpha glow strokes MAY remain as a cheap secondary when the bloom
flag is off, or as a low-cost contact glow under the bloom pass.

---

## 4. Feature flag & defaults (backward compatible)

Suggested setting (exact key TBD in P4.2):

- `CAMXORA_PREVIEW_HDR_BLOOM=0` (default) — current look  
- `=1` or Preferences toggle — HDR bloom path  

Existing templates MUST look unchanged with the flag off (REQ-P4.2 A1).

---

## 5. Integration points (no big-bang rewrite)

| Component | Change in P4.2+ |
|-----------|-----------------|
| `VideoSpectrumPreview.paintGL` | Optional offscreen HDR FBO; final blit + Alpha_Lock |
| `gpu_render` export loops | Same tonemap/bloom helpers for WYSIWYG |
| Shaders | New bloom downsample/upsample + tonemap programs |
| Diagnostics | Log whether HDR path active in `preview-gl-diag.log` |

Keep ModernGL + `QOpenGLWidget`. Do **not** migrate to Qt RHI/Vulkan under P4.

---

## 6. Performance budget

| Target | Gate |
|--------|------|
| Preview `paintGL` median | SHOULD stay &lt; 40ms at current preview size on mid GPU (existing hitch log) |
| Scrub mode (P2) | MAY disable bloom pyramid while interactive scrub is active |

---

## 7. Out of scope for this spike

- Implementing bloom shaders / FBOs (P4.2)
- Export parity wiring (P4.3)
- Playlist glass / DistroKid
- Changing frameless translucency (P3 decided keep)

---

## 8. Acceptance (REQ-P4.1)

- [x] A1: Sequence diagram scene → HDR → bloom → tonemap → opaque SDR FBO  
- [x] A2: Explicit note that Qt window alpha remains 1 after tonemap  

Next implementation step when scheduled: **REQ-P4.2** behind a flag with visual
parity when off.
