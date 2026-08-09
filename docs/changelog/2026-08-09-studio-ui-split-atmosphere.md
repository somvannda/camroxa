# Studio UI split + atmosphere preview pass

**Branch:** `feature/studio-v1`  
**Date:** 2026-08-09

## Summary

- Left rail is **Scene Tree only** (structure).
- **Browse assets** opens Asset Library as a discovery dialog (doc 08).
- Preview draws Session B **atmosphere** via `atmosphereDraw` (fog volume, rain/snow streaks, sky wash) — separate from particle emitters.

## Verify

```text
cd camxora_python
python -m pytest tests/test_studio_v1.py -q
```
