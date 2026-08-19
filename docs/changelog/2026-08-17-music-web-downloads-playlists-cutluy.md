# 2026-08-17 — Music web UX fixes, download gate, playlists, CutLuy checkout

## Summary

- Block free-tier MP3/WAV downloads in API and Create UI; removed MP3 from Free plan copy.
- Fix subscription/top-up checkout to use CutLuy `/v1/payments` (KHQR modal instead of broken redirect).
- Restore plan-specific purchase buttons (`Get Starter`, etc.).
- Align workspace row layout, unify Style/Weirdness/Audio Weight sliders.
- Add web music playlists (API + `/playlists` UI, public/private).

## Surfaces

- `platform_api`: download gate, CutLuy service, playlists migration `096`, playlist routes
- `music_web`: pricing modal, create page, sidebar, playlists pages, checkout modal

## Sandbox

- Deploy `platform_api` + run migration `096_web_music_playlists`
- Rebuild `music_web`
