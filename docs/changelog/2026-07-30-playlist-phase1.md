# Playlist Phase 1 — Title rename, looks, OFL fonts, glass chrome

**Date:** 2026-07-30  
**Status:** implemented (desktop local; full app restart required)  
**Spec:** `docs/playlist-domain-glass-polish.md`

## Summary

Right-rail **Title** is renamed to **Playlist**. Phase 1 adds six Playlist Looks (Split Stage, Glass Aurora, Neon Spectrum, Retro Vinyl, Noir Press, Gold Lacquer), playlist chrome fields (Now Playing, durations flag, track-count badge, glass panel sliders), and bundled OFL fonts (Inter, Montserrat, Rajdhani, Playfair Display, Bebas Neue, Source Serif 4). Timing controls remain plan-only. Spectrum glass is deferred (Phase 1b).

Follow-up polish (same day): preview now draws a **real glass panel plate** and a **NOW PLAYING pill** (not just glyph stroke / `▶` prefix). Layout labels are honest; **Split Stage (snap right/left)** snaps `titleX`/`titleY` when the Layout combo changes.

Follow-up: glass **card border was too faint / Pillow outline unreliable** — panel raster now draws a solid accent border ring + stronger fill so the list card frame is visible on dark video backgrounds.

Follow-up: **preview see-through** — soft glow / translucent overlays were writing framebuffer alpha &lt; 1, so Qt composited the app chrome through the preview. Preview (and lightning/particle passes that share the preview GL context) now use `blend_func_separate` so RGB blends normally while alpha stays opaque.


## Product impact

- **Before:** Tab labeled Title; typography presets only; OS fonts. Panel sliders only thickened text stroke; “list right” did not move the list; NOW PLAYING was a tiny `▶`. Soft glow / glass in the preview could show the desktop UI behind the OpenGL widget.
- **After:** Tab labeled **Playlist**. Pick a **Playlist Look** for layout + glass chrome + fonts/colors. **Glass panel** is a rounded frosted plate behind the list; **NOW PLAYING** is a pill badge above the active row. Layout **snap right/left** recenters the list; free-drag layouts stay free. Preview stays fully opaque over the app chrome.

## Technical impact

- Schema stays `titleText` (UI alias Playlist).
- New fields on `titleText` + draft keys `titleShowDurations`, `titleNowPlaying*`, `titleTrackCountBadge`, `titlePlaylistLook`, `titlePanel*`.
- `PLAYLIST_LOOK_PRESET_*` in `text_domain_registry.py`; `split_left` layout + `build_playlist_layout_side_draft_patch`.
- Bundled fonts under `camxora_python/assets/fonts/`; `system_fonts` resolves them first.
- Runtime emits `overlayKind=panel|pill` overlays; `gpu_render._render_panel_rgba` / `_render_overlay_rgba` shared by preview + export. Title drag moves panel/pill/badge with rows.

## Files touched

- `docs/playlist-domain-glass-polish.md`
- `camxora_python/assets/fonts/**`
- `camxora_python/features/video/lib/system_fonts.py`
- `camxora_python/features/video/lib/lightning_render.py` (opaque alpha blend for preview)
- `camxora_python/visualizer/gpu_render.py` (particle blend alpha lock)
- `camxora_python/features/video/lib/playlist_stage.py` (unused by Purple Neon Look; list-card is the goal)
- `camxora_python/features/video/lib/text_domain_runtime.py`
- `camxora_python/features/video/lib/text_domain_registry.py`
- `camxora_python/visualizer/gpu_render.py`
- `camxora_python/visualizer/preview_widget.py`
- `camxora_python/features/video/views/video_view.py`
- `camxora_python/tests/test_playlist_phase1.py`
- `camxora_python/features/video/widgets/right_rail.py`
- `camxora_python/features/video/widgets/text_domain_inspectors.py`
- `camxora_python/features/video/views/video_view.py`
- `camxora_python/visualizer/gpu_render.py`
- `camxora_python/visualizer/preview_widget.py`
- `camxora_python/tests/test_playlist_phase1.py`
- `docs/changelog/2026-07-30-playlist-phase1.md`
- `CHANGELOG.md`

## Migration / deploy

Desktop-only. Restart app. No API migrate. Existing templates keep working; enable Playlist and pick a Look. Re-pick **Layout → snap right/left** or a Playlist Look if the list was dragged off-side.

## Tests

- `pytest camxora_python/tests/test_playlist_phase1.py tests/test_text_styles_and_bg_grade.py` — 32 passed
- Panel chrome defaults stay off (`panelFrost` / `panelBorderWidth` = 0) so zero-stroke templates are preserved; Looks still apply glass values
- Added coverage for panel/pill overlays, layout side snap, `_render_panel_rgba` smoke, and **Purple Neon Glowing** (TRACKLIST header + active-row plate)

## Follow-ups

- Phase 1b: Spectrum glass material (shared plate language)
- Phase 2: more looks, true scene-sampled frost blur, durations from track probe, transport chrome
- Timing (gap/hardcover/opening): plan only — not implemented
