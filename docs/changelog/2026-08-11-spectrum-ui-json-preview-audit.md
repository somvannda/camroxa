# Spectrum UI ↔ renderer JSON ↔ live preview audit

**Date:** 2026-08-11  
**Branch:** `bugfix/preview-export-parity-gate`

## Path

UI draft key → `TemplateNormalizer.to_renderer_dict` / instance `audioSettings` + `layers[]` → `preview_widget.paintGL` / `gpu_render`.

## Controls with UI (Spectrum + Logo attach)

| UI control | Draft / layer key | Renderer JSON | Preview reads | Export reads | Notes |
|---|---|---|---|---|---|
| Enable Spectrum | `spectrumEnabled` | `spectrumEnabled` | yes | yes | OK |
| Preset | `style` | `style` + layer style resolve | yes | yes | OK |
| Stacked preset / Clear | layers stack | `layers` / instances | yes | yes | OK |
| Input Gain | `audioInputGain` | `audioSettings.inputGain` (+ alias `sensitivity`) | yes | yes | Per selected instance |
| Motion Smoothing | `audioMotionSmoothing` | `audioSettings.motionSmoothing` (+ alias `smoothing`) | yes (top-level envelope) | yes | Per-instance value mirrored; FFT smooth uses template/top path |
| Peak Hold Blend | `audioPeakHoldBlend` | `audioSettings.peakHoldBlend` | yes | yes | OK |
| Anchor / X / Y / Reset | `anchor`,`positionX/Y` | `position` / instance `x,y,anchor` | yes | yes | OK |
| Attach Spectrum to Logo | `spectrumAttachToLogo` | `previewBindings` + instance | yes | yes | Logo tab |
| Spectrum Outer Gap | `spectrumLogoGap` | `previewBindings.spectrumLogoGap` | yes | yes | Logo tab |
| Instance name/enabled/Add… | instance fields | `spectrumInstances[]` | yes | yes | OK |
| Layer Name | `name` | `layers[].name` | label only | label only | Not drawn |
| Circle Form | `curved`+`mirrored` | same | yes | yes | OK |
| Path Shape | `pathMode` | `layers[].pathMode` | yes | yes | OK |
| Ring Side | `gravity` | `layers[].gravity` | yes | yes | OK |
| Blend Mode | `blend_mode` | `layers[].blend_mode` | yes | yes | OK |
| Fill Circle / Solid Band / Floor Reflection | toggles | layer bools | yes | yes | OK |
| Global Height Gain | `audioBarHeight` | `audioSettings.barHeight` | yes | yes | OK |
| Bar Density | `barCount` | layer | yes | yes | OK |
| Bar Width | `barWidth` | layer | yes | yes | OK |
| Row Width | `linearSpan` | layer | **fixed 2026-08-11** | yes | Was ignored in preview |
| Raise Scroll | `frequencyScroll` | layer | **fixed 2026-08-11** | yes | Was ignored in preview |
| Bar Length | `thickness` | layer | yes | yes | OK |
| Layer Gap | `radiusOffset` | layer | yes | yes | OK |
| Opacity / Reflection Opacity | layer | layer | yes | yes | OK |
| Glow / Softness | `glow`,`blur` | layer | yes | yes | OK |
| Peak Caps + color/gap/size/decay | peakCap* | layer | yes | yes | OK |
| Color solid/gradient/dir/stops | `color.*` | layer.color | yes | yes | OK |

## In JSON / draft but **no Spectrum UI**

These are persisted via `build_spectrum_template_patch` and instance defaults, but **no inspector dial** and **neither preview nor export applies them to bar heights**:

- `audioBandContrast` → `bandContrast`
- `audioTransientFocus` → `transientFocus`
- `audioKickImpact` → `kickImpact`
- `audioBassEmphasis` → `bassEmphasis`
- `audioTrebleShimmer` → `trebleShimmer`
- `flyingGlowWingMotionSpeed` / `flyingGlowWingRelease`

Legacy Electron fields; safe in JSON, currently inert for rendering.

## Fix shipped with this audit

- `preview_widget.py`: apply `scroll_spectrum_heights(... frequencyScroll)` and pass
  `linear_span=linearSpan` into geometry (match export).
- `template_runtime.normalize_renderer_template`: keep `frequencyScroll` + `linearSpan`
  on normalized layers (were stripped, so legacy/single-layer paths lost UI values).
