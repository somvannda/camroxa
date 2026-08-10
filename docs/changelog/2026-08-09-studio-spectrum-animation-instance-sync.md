# Studio spectrum Animation sync into paint instances

**Date:** 2026-08-09  
**Branch:** `feature/studio-v1`

## Summary

Spectrum **Animation/behavior** looked dead while **Shape/type** still worked: live motion updated top-level `layers`, but GPU preview paints deep-copied `spectrumInstances[*].layers`.

## Fix

- `apply_live_composition_motion` now retunes and syncs `layers` + `audioSettings` into every `spectrumInstances` entry.
- Compile also bakes `animScale` onto spectrum layers (with rotation/opacity).
- Regression: `test_live_motion_syncs_spectrum_animation_into_instances`.

## Notes

- Desktop / preview path only; no sandbox deploy for this change.
- Play audio or scrub the playhead to see time-based behaviors (e.g. rotate); idle at `t=0` with no audio stays subtle for scale/opacity-driven animations.
