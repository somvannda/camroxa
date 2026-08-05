# Composition Engine P4 — materials (20)

**Branch:** `feature/composition-engine-p0-schema`  
**Date:** 2026-08-05

## Summary

Adds 20 spectrum material look packs. Applying a material changes glow/blur/blend
without changing geometry, so Neon/Glass/Fire/Plasma Circle reuse one shape.

## Verify

```text
pytest camxora_python/tests/test_composition_materials_p4.py -q
```
