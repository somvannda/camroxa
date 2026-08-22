# iOS Safari/Chrome packaged playback

**Date:** 2026-08-20  
**Branch:** `bugfix/music-web-ios-protected-playback`

## Summary

Encrypted playback used MSE `audio/mpeg` and a JS-only `new Audio()` node, which WebKit on iPhone does not play. The first iOS fix still failed: each chunk download re-fetched the whole B2 object, the `<audio>` element was 0×0, and `play()` ran on an empty src so the tap gesture never unlocked playback. iOS Now Playing also used the tiny SVG favicon.

## Product impact

**Before:** Play worked on desktop Chrome. iPhone Safari/Chrome did not play packaged tracks. Lock screen / Dynamic Island showed a small waveform in the corner of a white square and no track title.

**After:** iPhone play downloads the encrypted package once, decrypts it, and plays through an in-page `<audio playsinline>` (Web Audio if the element is blocked). Lock screen shows title, artist, and full cover art when the track has art, otherwise a full-bleed Camxora icon. Desktop Chrome still uses MSE.

## Technical impact

- `GET /web-music/licenses/segments/{token}?full=1` returns the CXA1 blob once (`X-Camxora-Chunk: all`).
- iOS decrypts that package with Web Crypto; chunked fetch remains the desktop MSE path and a fallback.
- Start a looping silent WAV on the in-page `<audio>` **synchronously in the tap** so later `play()` after decrypt is still allowed.
- Keep the element 1×1 CSS pixels in the viewport (not `h-0 w-0`).
- If HTMLAudio `play()` rejects, decode the MP3 with Web Audio on the AudioContext resumed in that tap.
- Packaged tracks no longer fall through to the ciphertext `/stream` URL.
- `navigator.mediaSession` metadata + play/pause/next/prev/seek/skip-10s handlers.
- Artwork: track `cover_url` at 96–512, else `/camxora-now-playing.png` (full-square PNG, not SVG).

## Files touched

- `platform_api/routers/web_music_licenses.py`
- `platform_api/tests/test_audio_packager.py`
- `music_web/src/components/player-provider.tsx`
- `music_web/src/lib/camxora-decrypt.ts`
- `music_web/src/lib/content-license.ts`
- `music_web/src/lib/ios-playback.ts`
- `music_web/src/lib/media-session.ts`
- `music_web/src/app/layout.tsx`
- `music_web/public/camxora-now-playing.png`
- `music_web/public/apple-touch-icon.png`
- `music_web/CHANGELOG.md`
- `platform_api/CHANGELOG.md`

## Migration / deploy

File-scoped: licenses router + music_web rebuild. No new Alembic revision.

## Tests

- `test_full_segment_returns_package_not_single_chunk`
- iOS Safari and Chrome: tap play, wait for one download/decrypt, audio starts; lock the phone and confirm title/artist/full art.
- Desktop Chrome: packaged play still works.
- Track with cover art uses that image on the lock screen, not the Camxora icon.

## Follow-ups

HLS/AAC remux would avoid holding a full decrypted MP3 in memory on iOS.
