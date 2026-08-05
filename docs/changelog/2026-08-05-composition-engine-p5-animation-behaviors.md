# Composition Engine P5 — animation behaviors (12)

**Branch:** `feature/composition-engine-p0-schema`  
**Date:** 2026-08-05

## Summary

Adds Layer 4 shared animation behaviors (Pulse … Breathing). The same behavior
id applies to Spectrum, Logo, Overlay, and Particles without changing spectrum
shape or material.

## Verify

```text
pytest camxora_python/tests/test_composition_animations_p5.py -q
```
