# Studio wiring gap pass — Expert palette, performance, post proxies

**Date:** 2026-08-09  
**Branch:** `feature/studio-v1`

## Summary

Audit found catalogs mostly unique; remaining preview gaps:

- Expert **palette intensity/saturation** now bake into gradient stops (not only a soft effect flag).
- Expert **performance quality / LOD** change spectrum `barCount` and particle spawn density.
- Post stack checks get broader **preview proxies** so more effects are visibly distinct.
- Lighting **trigger** bus drives live lightning intensity (not only audio-mapping → lighting).

## Notes

- Desktop / preview path; no sandbox deploy.
- NLE remains future-only.
