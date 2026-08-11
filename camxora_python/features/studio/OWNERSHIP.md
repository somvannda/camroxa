# Studio vs Video ownership

Composition Studio and the Video editor use **separate GPU engine packages**.
Do not share a mutable `visualizer/` tree between them.

| Concern | Own it under | Do not edit for the other page |
|---|---|---|
| Studio scene tree, inspectors, looks, documents | `features/studio/` | `features/video/` |
| Video inspectors, style registries, session presets | `features/video/` | `features/studio/` |
| Classic Video preview / export GPU | `visualizer_video/` | `visualizer_studio/` |
| Studio composition compile / looks GPU | `visualizer_studio/` | `visualizer_video/` |

When adding a Studio look/preset: put the recipe in `features/studio/lib/` and wire
Studio inspectors only. Do not add entries to
`features/video/lib/spectrum_style_registry.py` unless the Video page explicitly
needs the same preset.

Video composition-axis UI (if any) must use Video-local catalogs under
`features/video/lib/composition_*.py` and must **not** import `visualizer_studio`.
