# Split Video vs Studio GPU engines

## Summary

Video and Composition Studio no longer share a mutable `camxora_python/visualizer/`
package. Video uses a dedicated classic engine package; Studio keeps the
composition-aware engine under its own package name.

## Packages

| Package | Role |
|---|---|
| `camxora_python/visualizer_video/` | Video GPU — byte-aligned to `origin/main` desktop **1.2.4** `visualizer/` (renamed package only) |
| `camxora_python/visualizer_studio/` | Studio composition engine (former shared `visualizer/`) |

Shared `visualizer/` was removed so Studio work cannot mutate Video’s engine.

## Video page aligned to desktop 1.2.4

`camxora_python/features/video/` matches `origin/main` (desktop 1.2.4) exactly aside
from `visualizer` → `visualizer_video` import/CLI rewires. Includes the 1.2.3/1.2.4
multi-bolt lightning export fixes. Composition-axis Video UI from the Studio-era
branch was removed so the Video page is the 1.2.4 editor again.

## Feature wiring

- Video preview / export / CLI → `visualizer_video` (`preview_widget`, `gpu_render`,
  `visualizer_video.main` / `.daemon`).
- Studio preview / export / looks → `visualizer_studio` (including
  `document_to_renderer_dict` and Prism Core Glow compile).
- Studio shape→style aliases live in `visualizer_studio.presets.shapes` (no Video
  composition helper dependency).

## Intentional tradeoff

Video does not use the Studio composition engine. Studio-only looks (Prism Core Glow)
stay under `features/studio/` + `visualizer_studio`.
