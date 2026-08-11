# 2026-08-11 — Lightning export timing (per-bolt floors)

## Summary

1.2.3 restored multi-bolt **visibility** with a **global** flash floor (any
peak → raise every layer). That matched older dense export but **wrong timing**
vs preview / `bugfix/preview-export-parity-gate`.

1.2.4 restores **per-layer** floors (parity-branch behavior) and keeps the
floor-math fix so sparse peaks are not crushed below the draw threshold.

## Changes

- `run_gpu_render` passes `flash_overrides_by_layer` again (not global-only).
- `apply_lightning_flash_floor` unchanged (correct opacity conversion).
- Tests cover sparse-only raise + double-scale regression.

## Surfaces

- Desktop only.
