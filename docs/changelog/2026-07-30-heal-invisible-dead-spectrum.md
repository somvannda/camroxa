# Heal invisible / dead spectrum on some templates

**Date:** 2026-07-30  
**Status:** implemented (desktop local; restart + re-open template)

## Summary

Some templates (notably **Thunder Bass 29July**) looked like spectrum styles were broken and/or showed a “dead” ring. Root causes were fully transparent layers (`opacity: 0` on every ring) and extreme motion smoothing (`~0.99`). Hydrate now heals those cases; style presets always restore visible opacity.

## Product impact

- **Before:** Thunder Bass 29July — all rings opacity 0 → styles appeared to do nothing; templates with motionSmoothing 0.99 looked frozen.
- **After:** Opening the template restores opacity when every ring is invisible; applying any style forces a visible opacity; motionSmoothing > 0.95 soft-clamps to 0.85 on hydrate. Local catalogs already repaired for affected templates.

## Technical impact

- `heal_spectrum_layer_visibility()` on hydrate
- `build_spectrum_preset_template` always sets visible opacity
- STYLE patches default `opacity: 1.0`
- Local `video-templates.json` repaired for Thunder Bass 29July / Bass Vortex / over-smoothed Thunder Bass & Bass Ignition

## Files touched

- `camxora_python/features/video/lib/spectrum_style_registry.py`
- `camxora_python/features/video/views/video_view.py`
- `camxora_python/tests/test_spectrum_vivid_and_position.py`
- `docs/changelog/2026-07-30-heal-invisible-dead-spectrum.md`
- `CHANGELOG.md`
- Local Camxora user `video-templates.json` (opacity/smoothing heal)

## Migration / deploy

Desktop-only. Fully restart Camxora, open **Thunder Bass 29July**, play preview, try switching styles.

## Tests

- `pytest camxora_python/tests/test_spectrum_vivid_and_position.py`

## Incident

- Template: Thunder Bass 29July (`nebula-pulse-camxora-v1`) — all 4 layers `opacity: 0`
- Also: Thunder Bass / Bass Ignition `motionSmoothing: 0.99` → dead-looking reactivity
