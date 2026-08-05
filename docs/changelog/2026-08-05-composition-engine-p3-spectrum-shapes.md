# Composition Engine P3 — spectrum shapes (15)

**Branch:** `feature/composition-engine-p0-schema`  
**Date:** 2026-08-05

## Summary

Adds a 15-id spectrum geometry catalog and path generators (polygon / heart /
infinity / spiral / tunnel) so shapes render in preview/export while staying
independent of material and palette.

## Verify

```text
pytest camxora_python/tests/test_composition_spectrum_shapes_p3.py -q
```
