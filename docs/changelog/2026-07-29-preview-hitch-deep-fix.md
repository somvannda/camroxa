# Preview hitch deep fix: no paintGL framebuffer grab

**Date:** 2026-07-29  
**Status:** implemented (desktop)

## Summary

Periodic preview freezes every ~4–5 seconds came from `paintGL` still calling `grabFramebuffer()` on a ~2.5s cadence whenever audio was **not** marked playing (paused scrubbing, track end, or any frame where play-state flipped). That GPU pipeline stall feels like a regular hitch. Draft/API sync timers were checked and are **not** the primary cause (local draft persist is debounced; music-download / pipeline polls run on worker threads).

## Product impact

- **Before:** Preview stutter every few seconds while paused or when freeze-frame caching ran from the 60fps paint loop.
- **After:** No framebuffer grab inside `paintGL`. One-shot snapshot only on pause/stop/track-end for export freeze UX. Fewer per-frame allocations (FFT buffer reuse, VBO writes without `.tobytes()`). Hitch breadcrumb logs when a frame exceeds 40ms.

## Technical impact

Root cause ranking for the ~4–5s rhythm:

1. **Primary:** `grabFramebuffer` from `paintGL` finally (throttled ~2.5s when `audio_playing` is false) — removed.
2. **Secondary:** GC pressure from per-frame `np.interp(...).astype` + `arr.tobytes()` VBO uploads — mitigated.
3. **Ruled out / low:** template draft disk persist (200ms debounce on edits only); music download 4s / video pipeline 6s polls (worker threads; UI only gets light signals).

## Files touched

- `camxora_python/visualizer/preview_widget.py`
- `camxora_python/visualizer/audio.py`
- `camxora_python/features/video/lib/lightning_render.py`

## Migration / deploy

- Desktop-only. Restart Camxora. Play and pause preview for 30s+; hitch should be gone.
- If a hitch remains, check console / preview log for `preview hitch … Xms` lines.

## Tests

- Manual playback soak.
- Syntax/import smoke via pytest lightning suite (no paintGL harness).

## Follow-ups

- If hitch persists only with Motion Trails + high particle count, profile trail quad allocations next.
- Optional: pause shell sync coordinators while Video page is focused and playing.
