# music.camxora.com: free V6 Pro / V6 Wild previews

## Summary

Free-plan users can now try **V6 Pro** and **V6 Wild** before buying a pack.
Each model is limited to **one preview per billing month**, and a preview is the
first **60 seconds** of the generated track. The rest of the Free plan's 50
monthly credits can still be spent on full-length **V6 Mini** tracks.

Previews are **play-only**. MP3, WAV, LRC and SRT exports stay locked, and the
UI shows a **Preview** badge with an **Extend preview → buy a pack** action.
Buying any credit pack restores full-length generation and downloads.

## Product impact

- Free plan: 1 × V6 Pro preview + 1 × V6 Wild preview + 3 × V6 Mini = 5 songs
  per billing month.
- A second V6 Pro / V6 Wild request returns a clear "preview used" upsell
  instead of silently downgrading to V6 Mini.
- Paid subscribers and anyone holding purchased/admin credits are unaffected and
  continue to receive full-length tracks.
- `admin.camxora.com` shows which generated tracks are previews.

## Technical impact

- New migration `143_web_music_free_previews`:
  - `suno_tasks.is_preview`, `preview_seconds`, `preview_released`
  - `web_music_preview_entitlements` (user, period, model) for race-safe quota
- `WebMusicService` reserves the preview slot before charging, releases it on
  failed submissions, and marks the `suno_tasks` row.
- Audio is trimmed **server-side before B2 upload/encryption** (MP3 + WAV). Any
  on-demand fallback (B2 miss / Suno fallback) is trimmed again, and refuses to
  serve if ffmpeg cannot cut it.
- Web-music quota responses expose `previews` so the Create page can show
  remaining previews.
- Download endpoints reject preview tasks with `preview_download_blocked`.
- `music_web` model labels are now **V6 Pro / V6 Mini / V6 Wild**; preview rows
  hide MP3/WAV/LRC/SRT and show the Extend preview CTA.
- `admin_portal` generated-song views show the preview badge and length.

## Migration / deploy

- Apply `143_web_music_free_previews` to sandbox and production.
- Ensure `ffmpeg` is installed on API/worker hosts; preview ingest and fallback
  playback require it.

## Tests

- `platform_api/tests/test_web_music_previews.py`
- `music_web` `clip-display` tests
