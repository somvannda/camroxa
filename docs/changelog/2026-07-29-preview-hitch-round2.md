# Preview hitch round 2: skip redundant template pushes + back off sync while playing

**Date:** 2026-07-29  
**Status:** implemented (desktop)

## Summary

Preview still hitched every few seconds after removing `paintGL` framebuffer grabs. Remaining causes: (1) every draft/preview push called `set_template` → full `normalize_renderer_template` + peak-cache clear even when content was identical; (2) particle VBO uploads still used `.tobytes()` each frame (GC spikes); (3) lightning peak-flash math ran every frame even when unused; (4) music-download (4s) / video-pipeline (6s) workers contended with the UI while preview played.

## Product impact

- **Before:** Periodic lag every few seconds during Video preview playback.
- **After:** Identical template pushes are skipped; particle uploads avoid byte copies; lightning peak flash only runs when needed; background download/pipeline polls back off while preview is playing.

## Technical impact

- `stage_panel.set_renderer_preview` only calls `set_template` when template JSON fingerprint changes.
- `VideoSpectrumPreview.set_template` fingerprints payload and skips normalize/cache clear when unchanged.
- `_render_particle_styled_quads` writes contiguous ndarray (no `.tobytes()`).
- Preview paint skips `peak_lightning_flash` unless lightning is on and brightness/vignette react needs it.
- `MusicDownloadCoordinator.set_preview_playing` / `VideoPipelineCoordinator.set_preview_playing` stretch poll intervals while playing.

## Files touched

- `camxora_python/features/video/widgets/stage_panel.py`
- `camxora_python/visualizer/preview_widget.py`
- `camxora_python/visualizer/gpu_render.py`
- `camxora_python/shared/services/music_download_coordinator.py`
- `camxora_python/shared/services/video_pipeline_coordinator.py`
- `camxora_python/features/video/views/video_view.py`
- `camxora_python/app/application.py`

## Migration / deploy

- Desktop-only. Restart Camxora fully (not just reload template).

## Tests

- `pytest camxora_python/tests/test_lightning_layers.py camxora_python/tests/test_music_download_coordinator.py` — 17 passed.
- Manual: play preview 30–60s with Lightning + particles on; hitch should be gone or rare.

## Follow-ups

- If hitch remains only with trails/high particle counts, profile trail quad allocations next.
- Consider moving draft `json.dumps` fingerprinting off the UI thread for huge templates.
