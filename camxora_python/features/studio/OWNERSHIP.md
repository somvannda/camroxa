# Studio vs Video ownership

Composition Studio and the Video editor share the GPU preview/export engine under
`visualizer/`, but **feature UI and presets must stay page-owned**.

| Concern | Own it under | Do not edit for the other page |
|---|---|---|
| Studio scene tree, inspectors, looks, documents | `features/studio/` | `features/video/` |
| Video inspectors, style registries, session presets | `features/video/` | `features/studio/` |
| Shared render/compile for both | `visualizer/` | Prefer additive flags keyed by Studio document fields |

When adding a Studio look/preset: put the recipe in `features/studio/lib/` and wire
Studio inspectors only. Do not add entries to
`features/video/lib/spectrum_style_registry.py` unless the Video page explicitly
needs the same preset.
