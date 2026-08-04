# 2026-08-04 — Export WYSIWYG spectrum/logo parity + logo Reset Center

## Summary

Export was not matching the live Video preview: spectrum (and related style
offsets) used top-level template fields instead of multi-instance jobs, pipeline
export preferred the saved template over the live draft, and the Logo inspector
lost **Reset Center**.

## Changes

- Export GPU path iterates `_spectrum_draw_jobs` / `spectrumInstances` (per-instance
  style, position, attach/gap, audio) so rendered spectrum matches preview.
- Pipeline + manual export ship live draft, flushed layers, and
  `spectrum_instances`.
- Lightning export accepts `flash_override` so short strikes are not missed at
  encode fps (keeps preview `opaque_framebuffer_alpha`).
- Logo inspector **Reset Center** restored (centers logo; spectrum when attached).

## Surfaces

- `camxora_python` desktop only (no sandbox deploy required for this fix).
