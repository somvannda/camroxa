# 2026-08-09 — Lightning max 10 layers (preview + export)

## Summary

Lightning layer stacks are capped at **10 bolts**. Preview and export already
shared `render_lightning_layers_gl` for every layer; this change makes the
product budget explicit, clamps templates that exceed it, and locks Add/Dup at
the cap.

## Changes

- `MAX_LIGHTNING_LAYERS = 10` in `lightning_style_registry`.
- `normalize_lightning_layers` truncates to 10 (preview, save, export).
- Video page Add/Dup refuse a larger stack with a warning toast.
- Lightning layer editor disables Add/Dup at 10 and updates copy.
- Tests cover the cap and export normalizer keeping all 10 layers.

## Surfaces

- `camxora_python` desktop only (no sandbox deploy).
