# Studio wiring polish (scroll pickers + export panel)

**Date:** 2026-08-09  
**Branch:** `feature/studio-v1`

## What changed

- Axis catalogs in Studio inspectors use horizontal **scroll chip pickers** instead of dropdowns.
- Background motions get stronger per-id signatures (`userScale`, offsets, zoom/vibrate strengths, warp proxies) so options do not collapse into lookalikes.
- Studio **Export** panel: resolution, fps, quality (speed mode), include-audio + range fields persisted on `studioExport` and wired into the manual export request.
- Wiring matrix documented in `docs/COMPOSITION_STUDIO_WIRING.md`.

## Explicitly deferred

Full NLE timeline (clips / razor / transitions / keyframes / nested / mixer) remains a future build.
