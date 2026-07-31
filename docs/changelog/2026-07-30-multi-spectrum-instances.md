# Multi-Spectrum instances

**Date:** 2026-07-30  
**Status:** implemented (desktop local; full app restart required)

## Summary

You can now stack up to **8 independent Spectrums** — each with its own name, enable flag, position, attach-to-logo, audio knobs, style, and ring-layer stack — similar to Lightning bolts. Legacy templates with a single `layers[]` stack migrate automatically to one Spectrum instance.

## Product impact

- **Before:** One Spectrum with multiple ring layers sharing one position/audio.
- **After:** Spectrum tab → **Spectrums** combo: **Add / Dup / Del / Up / Down**. Select a Spectrum, then edit its rings below. Drag the preview to place the **selected** Spectrum. New Spectrums default to detached (+offset) so they don’t sit on top of the first.

### How to use

1. Open **Spectrum**
2. In **Spectrums**, click **Add** (or **Dup**)
3. Select each Spectrum in the combo
4. Drag preview to place it; tune attach / audio / style / ring layers per Spectrum
5. Disable one without deleting via its **Enabled** checkbox

## Technical impact

- New `spectrumInstances[]` on templates; `spectrum_instance_registry.py` migrate/normalize/mirror
- Preview paint loops all enabled instances with independent centers
- VideoView keeps working `_spectrum_layers` as the selected instance’s rings
- Instance[0] mirrored to legacy `layers` / `position` / `audioSettings` for packs
- Logo drag restored on Logo tab (`logoSettings.position` when detached)

## Files touched

- `camxora_python/features/video/lib/spectrum_instance_registry.py`
- `camxora_python/features/video/widgets/spectrum_instance_editor.py`
- `camxora_python/features/video/widgets/spectrum_inspector.py`
- `camxora_python/features/video/views/video_view.py`
- `camxora_python/features/video/lib/video_template_save.py`
- `camxora_python/features/video/services/template_normalizer.py`
- `camxora_python/visualizer/template_runtime.py`
- `camxora_python/visualizer/preview_widget.py`
- `camxora_python/visualizer/gpu_render.py` (helper)
- `camxora_python/tests/test_spectrum_instances.py`
- `docs/changelog/2026-07-30-multi-spectrum-instances.md`
- `CHANGELOG.md`

## Migration / deploy

Desktop-only. Fully restart the app. Existing templates become one Spectrum automatically.

## Tests

- `pytest camxora_python/tests/test_spectrum_instances.py`

## Follow-ups

- Wire all GPU export paths to loop `_spectrum_draw_jobs` (preview already loops; export currently mirrors instance[0] for pack compat — extend export loops next).
- Cap UI warning when approaching 8 instances under heavy glow.

## Incident — missing / dead spectrum after multi-instance (2026-07-30)

**Symptom:** Some templates lost their spectrum; others showed a static (“dead”) ring with no audio reactivity.

**Root cause:**
1. Empty `spectrumInstances[].layers` took priority and mirrored over healthy top-level `layers`, wiping rings on preview/save.
2. Legacy `audioSettings.sensitivity` / `smoothing` were not mapped into `inputGain` / `motionSmoothing` when building instances, so gain reset and preview often read the wrong knob.

**Fix:** Heal empty instance layers from template `layers`; preserve working layers on save/mirror; coerce sensitivity↔inputGain + smoothing↔motionSmoothing; preview reads `inputGain` with sensitivity fallback.

**Verify:** Fully restart desktop app, re-open affected templates, play preview — spectrum rings should move with audio again.

## Incident — Magma Ridge (waveform styles) not applying (2026-07-30)

**Symptom:** Selecting **Magma Ridge** (also Aurora Ribbon / Plasma Bloom) did not show the ridge waveform — preview kept the previous bar look.

**Root cause:** Multi-Spectrum preview draws each instance’s own `style`. Preset apply updated the flat draft + layers but did not sync `style` onto the selected `spectrumInstances[]` entry, and often skipped a preview flush — so the renderer kept the old bar style id.

**Fix:** Flushing the selected Spectrum instance now copies draft style/audio + layers; preset/stack/restore paths call `_commit_spectrum_preset_to_preview()`.

**Verify:** Restart app → Spectrum preset → **Magma Ridge** — should show a filled ridge/mountain waveform, not orbit spikes.
