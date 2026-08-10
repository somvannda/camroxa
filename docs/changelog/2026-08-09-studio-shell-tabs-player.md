# Studio shell — Video-matched layout

**Date:** 2026-08-09  
**Branch:** `feature/studio-v1`

## Summary

Studio workspace now follows the Video page chrome:

- Fixed **left 420** Composition Studio (scene tree + inspectors)
- Flexible **center stage** (Preview → Playback card → TRACK LIST | Actions)
- Fixed **right 380** Inspector (AI / Developer tabs)
- Shared `#video_workspace` QSS (`account_card` rails)

Custom center-stage / half-width right-tab experiment was reverted in favor of this Video pattern.

## Notes

- Desktop UI only; no sandbox deploy.
