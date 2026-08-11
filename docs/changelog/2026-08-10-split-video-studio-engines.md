# Split Video vs Studio GPU engines

## Summary

Video and Composition Studio no longer share a mutable `camxora_python/visualizer/`
package. Video uses a frozen classic engine; Studio keeps the composition-aware
engine under its own package name.

## Packages

| Package | Role |
|---|---|
| `camxora_python/visualizer_video/` | Classic Video GPU (snapshot of pre-composition-hard-cut engine) |
| `camxora_python/visualizer_studio/` | Studio composition engine (former `visualizer/`) |

Shared `visualizer/` was removed so Studio work cannot mutate Video’s engine.

## Feature wiring

- Video preview / export / CLI → `visualizer_video` (`preview_widget`, `gpu_render`,
  `visualizer_video.main` / `.daemon`).
- Studio preview / export / looks → `visualizer_studio` (including
  `document_to_renderer_dict` and Prism Core Glow compile).
- Video `TemplateNormalizer` restored to classic merge → strip `composition` →
  text inject (no `composition_renderer`).
- Video composition-axis catalogs stay under `features/video/lib/composition_*`
  and must not import `visualizer_studio`.

## Intentional tradeoff

Video composition-axis features that depended on the post-hard-cut composition
engine regress relative to that era; classic templates remain the Video GPU path.
