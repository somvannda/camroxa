# Composition Engine V1 — hard cut

**Branch:** `feature/composition-engine-v1`  
**Date:** 2026-08-05

## Summary

Replaces legacy-adapter P0–P6 with an engine-true compile path: composition JSON
is required, catalogs live under `visualizer/presets`, and preview/export consume
`compile_scene` output. Old style-only templates fail closed.

## Verify

```text
pytest camxora_python/tests/test_composition_engine_v1.py -q
```
