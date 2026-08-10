# Studio Expert inspectors + preview fidelity

**Date:** 2026-08-09  
**Branch:** `feature/studio-v1`

## Summary

- Timeline is pinned under the Studio shell (fixed height) so the 16:9 preview can no longer squeeze it off-screen. Visible in Creator/Expert; hidden in Beginner/Developer.
- Expert mode exposes denser axis controls (brightness/contrast, bar height/glow, camera pan/zoom/shake, particle spawn/size, lighting intensity, post amount, performance, audio gain/smoothing).
- Preview fidelity: expert tuning bridges into GPU template keys; background **video plate** (mp4/mov/…) decodes via OpenCV and updates the GL background texture on the playhead.

## Notes

- Video page remains frozen.
- AI Designer still rule-based.
- Marketplace/cloud still stubs.
