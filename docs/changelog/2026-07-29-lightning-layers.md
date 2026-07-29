# Lightning layers (background bolts)

**Date:** 2026-07-29  
**Status:** implemented (A/B/C complete — preview + export draw parity)

## Summary

Adds a **Lightning** domain tab with multi-layer bolts. Users can stack as many lightning layers as they want; each layer has its own style, color, flash/reactivity settings, and free X/Y position. Dragging the preview while the Lightning tab is active moves the selected bolt (same free-position pattern as Spectrum).

**One layer = one bolt** (Storm/Spider no longer spawn multi-bolt fans). Want more strikes → Add layers. **Motion / Grow Speed** stretches bolt reach as well as flash timing.

- Free **Rotation** 0–360° per bolt (on top of Direction presets).
- Flash timing is **discrete strike windows** — bass no longer keeps a constant multi-bolt glow on. Shape is locked for the duration of each strike. Branchiness adds at most two small twigs on that one bolt.

Phases **A / B / C** are complete: core controls, style polish + triggers, presets + seed lock, and shared preview/export draw via `lightning_render.py`.

## Product impact

- **Before:** No background lightning effect; only Spectrum/Particles atmosphere.
- **After:** Left rail → **Lightning**. Enable the effect, Add/Dup/Del/reorder layers, pick one of 10 styles per layer, and drag on the preview to place each bolt freely.
- **Phase B:** Branchiness / Thickness / Glow + Trigger modes (always / timed / audio / kick / beat) with threshold.
- **Phase C:** Bolt Presets (Neon Sky, Ground Strike, Sheet Flash, Pulse Bloom, Horizon Band, Storm Fork) + Lock Seed for a stable jagged shape; export matches preview.

Default templates keep `lightningEnabled: false` so existing looks are unchanged until the user turns Lightning on.

## Technical impact

- Template keys: `lightningEnabled`, `lightningLayers[]` (normalized in `template_runtime`).
- Per-layer: `trigger`, `triggerThreshold`, `seed`, `seedLock`, `glow`, `branchiness`, `thickness`, etc.
- Shared GL helper `render_lightning_layers_gl` used by preview and all three `gpu_render` draw paths.
- Free-position edit mode: `resolve_preview_edit_modes` 4-tuple; `lightning_position_changed` signal.
- Save/draft dirty tracking mirrors Spectrum layers (`lightningLayers` in draft store + save patch).
- `seedLock=True` freezes shape time/seed; flash still follows trigger + flashRate/speed.

## Files touched

- `camxora_python/features/video/lib/lightning_style_registry.py`
- `camxora_python/features/video/lib/lightning_geometry.py`
- `camxora_python/features/video/lib/lightning_render.py`
- `camxora_python/features/video/widgets/lightning_layer_editor.py`
- `camxora_python/features/video/widgets/lightning_inspector.py`
- `camxora_python/features/video/widgets/left_rail.py`
- `camxora_python/features/video/widgets/stage_panel.py`
- `camxora_python/features/video/lib/preview_edit_modes.py`
- `camxora_python/features/video/lib/template_draft_domains.py`
- `camxora_python/features/video/lib/video_template_draft.py`
- `camxora_python/features/video/lib/video_template_save.py`
- `camxora_python/features/video/services/template_normalizer.py`
- `camxora_python/features/video/services/video_draft_store.py`
- `camxora_python/features/video/views/video_view.py`
- `camxora_python/visualizer/template_runtime.py`
- `camxora_python/visualizer/preview_widget.py`
- `camxora_python/visualizer/gpu_render.py`
- `camxora_python/tests/test_lightning_layers.py`
- `camxora_python/tests/test_preview_edit_modes.py`

## Migration / deploy

- Desktop-only. Restart the app to load Python modules.
- No API/DB migration. Existing templates get empty/default lightning layers with effect off until enabled.

## Tests

- `pytest camxora_python/tests/test_lightning_layers.py camxora_python/tests/test_preview_edit_modes.py` — 18 passed.

## Follow-ups

- Richer per-layer color editor (gradient stops) beyond solid/first-stop preview color.
- Optional effect packs for Lightning.
- **Next product track:** multi-Spectrum instances (independent Spectrum stacks with full controls each).
