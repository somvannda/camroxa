# Studio background motion + atmosphere fidelity

**Date:** 2026-08-09  
**Branch:** `feature/studio-v1`

## Summary

- Fixed rain/snow/storm falling **down** in NDC (was flying upward).
- Each atmosphere style now has a distinct GPU draw (weather streaks, dust motes, cloud bands, aurora ribbons, heat shimmer, caustics, stars) instead of only a shading filter.
- Expert knobs for **Motion** (speed / amplitude / zoom / warp) and **Atmosphere** (density / speed / opacity / wind).
- Secondary atmosphere post proxies were softened so they no longer dominate the look.

## Notes

- Desktop preview path; no sandbox deploy.
- Play/scrub the Timeline player bar to see time-based motion and falling weather.
