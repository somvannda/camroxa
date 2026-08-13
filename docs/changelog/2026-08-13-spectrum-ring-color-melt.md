# 2026-08-13 — Spectrum closed-ring color seam melt

**Date:** 2026-08-13  
**Surfaces:** `camxora_python` (preview + Manual + Auto-Video / export)  
**Branch:** `bugfix/spectrum-ring-color-melt`

## Summary

Full-circle spectrum gradients had a hard color cut where the first and last
stops meet. All five UI Gradient directions now melt on closed rings:

| UI label | Key | Melt behavior |
|----------|-----|----------------|
| Around Ring | `left-to-right` | Wrap last→first + neighbor wash |
| Base to Tip | `top-to-bottom` | Multi-stop base/tip soften |
| Radial (Base to Tip) | `radial` | Same as Base to Tip |
| Circular (Around Ring) | `circular` | Same as Around Ring |
| Diagonal (Around + Tip) | `diagonal` | Around-ring wrap + softer tip blend |

Bass Drive uses `diagonal` — previously skipped wrap because only
`left-to-right`/`circular` were treated as ring modes.

## Verify

1. Full-circle layer; try each Gradient dropdown value.
2. Confirm no hard seam at the top of the ring.
3. Preview / Manual / Auto-Video match.
