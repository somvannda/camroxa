# Web music workspace track list UI

## Summary
- Flatten generated tracks so each Suno variant is its own row with the song title (no Version 1/2 grouping).
- Show Suno cover art per track in the list and detail panel.
- Fix horizontal overflow from long style strings and nested button layout.
- Always show vocal gender, style influence, weirdness, and audio weight in the right panel.
- Persist advanced create settings and Suno cover URLs on the API.
- Add **Add to playlist** on each workspace track (list + detail panel).
- Fix create flow so slider defaults (0.50) and vocal gender (including Both) are saved and displayed.
- Download **LRC** and **SRT** timed lyrics per track (Suno karaoke timestamps; free for all users).
- Playlist detail page redesigned with Suno-style hero, search/sort, cover art rows, and add-songs panel.

## Surfaces
- `music_web` Create workspace list + detail panel
- `platform_api` web music generations API + migration `098_web_music_suno_cover_urls`
