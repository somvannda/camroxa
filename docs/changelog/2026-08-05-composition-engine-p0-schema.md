# Composition Engine P0 — scene schema freeze

**Branch:** `feature/composition-engine-p0-schema`  
**Date:** 2026-08-05

## Summary

Locks the composition architecture-tree JSON under template `composition` (version 1), with Layer 1 scene objects including distinct **Text** and **Overlay**. Legacy GPU fields stay authoritative for preview/export; `TemplateNormalizer` strips `composition` from the renderer dict.

## Changes

- `camxora_python/features/video/lib/composition_scene_contract.py` — defaults, normalize, legacy projection, ensure/strip helpers
- `camxora_python/features/video/lib/video_template_save.py` — save patch attaches derived `composition`
- `camxora_python/features/video/services/template_normalizer.py` — strip `composition` before GPU dict
- `docs/COMPOSITION_ENGINE_P0_SCENE_SCHEMA.md` — frozen key table
- Tests + `composition_default_scene.json` fixture
- Note: `test_video_template_fixtures` exact golden equality for titleText
  playlist glass fields is already stale on current `main` tip (unrelated to
  `composition`); P0 asserts strip via dedicated contract tests instead.

## Verify

```text
pytest camxora_python/tests/test_composition_scene_contract.py camxora_python/tests/test_video_template_fixtures.py -q
```
