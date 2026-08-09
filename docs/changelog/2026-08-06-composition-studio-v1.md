# Composition Studio v1 — sidebar greenfield page

**Branch:** `feature/studio-v1`  
**Date:** 2026-08-06

## Summary

Adds a **Studio** workspace route beside Video. Studio is built from the
Motion Graphics Platform docs (scene tree + axes inspectors + compile preview).
Video remains the production export/pipeline console and is not further
refactored for Studio UX.

## Verify

```text
cd camxora_python
python -m pytest tests/test_navigation.py tests/test_studio_v1.py -q
```

## Regression note

Video page code paths are intentionally untouched by Studio feature work
beyond shared navigation registration. Open Video separately to confirm
export/pipeline still loads.
