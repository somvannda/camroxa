# 2026-08-11 — Multi-bolt lightning export fix

## Summary

1.2.2 export used sparse per-layer flash floors so only bolts that peaked in
the encode window were raised. With 4–5 positioned layers that often looked
like a single bolt in the MP4. Export again uses a **global** flash floor
(any peak → raise all enabled layers) while keeping 60 Hz interval sampling
so short strikes are not missed. Sampler peak floors are applied without a
second intensity×opacity multiply.

## Changes

- `run_gpu_render` passes `flash_override=global_peak` (not sparse by-layer map).
- `apply_lightning_flash_floor` converts sampler peaks into pre-opacity flash space.
- `_set_lightning_layers` schedules a preview update.
- Regression tests in `test_lightning_multibolt_export.py`.

## Surfaces

- `camxora_python` desktop only (no API deploy).
