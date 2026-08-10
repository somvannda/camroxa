# Prism Core Glow — Trap Nation-style multi-layer spectrum (Studio-only)

## Summary
New Spectrum **Look → Prism Core Glow** in Composition Studio only: three stacked
rings (soft rainbow aura, rainbow body, white core). Recipe lives under
`features/studio/lib/spectrum_looks.py` — **Video page presets are unchanged**.

## Ownership
| Surface | Path |
|---|---|
| Studio look recipe / UI | `features/studio/lib/spectrum_looks.py`, Spectrum inspector |
| Shared GPU compile (composition docs) | `visualizer/scene/*` |
| Video stacked presets | `features/video/lib/spectrum_style_registry.py` (not modified) |

## Surfaces
- Desktop Studio Spectrum inspector (Look combo)
- Preview / export for Studio composition documents
