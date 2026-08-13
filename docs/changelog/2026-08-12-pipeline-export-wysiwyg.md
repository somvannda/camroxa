# 2026-08-12 — Pipeline Auto-Video Manual Export WYSIWYG

**Date:** 2026-08-12  
**Surfaces:** `camxora_python` (desktop only)  
**Branch:** `bugfix/pipeline-export-wysiwyg`

## Summary

Spectrum glow melt + full saved-template look for **all three** paths:

| Path | Melt source |
|------|-------------|
| Preview | PR #37 glow blend (`SRC_ALPHA, ONE` + dual glow passes) |
| Manual Export | Same GPU path + live template domains |
| Auto-Video / Progress pipeline | Same GPU path + saved template now passes `spectrumInstances` / lightning (was dropping them) + Manual encode defaults so glow is not skipped |

## Changes

- `TemplateNormalizer.from_saved_workspace` / `build_saved_workspace_renderer_dict`
- `PipelineAutomationService` uses the helper and Manual-tier encode path
- Auto speed refuses silent `very_fast`/`draft` unless tier is explicitly Draft (keeps dual glow melt)
- Save patch: `lightning_layers=None` keeps saved bolts (no single default bolt)
- Regression: `tests/test_pipeline_saved_template_parity.py`

## Intentional differences kept

- Pipeline still swaps in the AI run background (preview bg cleared)
- Output paths / merge / billing remain pipeline-specific
