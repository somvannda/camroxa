# iOS Safari playback without weakening protected audio

**Date:** 2026-08-21  
**Branch:** `bugfix/ios-safari-playback`  
**Surfaces:** music_web

## Summary

iOS Safari cannot play packaged Camxora audio through MSE `audio/mpeg` (Version 2 error: “The operation failed for an operation-specific reason”). Unpackaged Version 1 could show a moving progress bar with no sound (`new Audio()`, CORS `crossOrigin`, lost tap-to-play gesture).

The Safari/iOS path decrypts license chunks in memory and plays them with Web Audio. It does **not** build a downloadable `blob:` / `data:` MP3. Chrome still uses MSE. Packaged tracks no longer fall back to the clamped play proxy (that proxy is ciphertext once packaged).

## Product impact

- iPhone Safari should play both versions with sound.
- Protection rules stay in force: no Suno/B2 URLs in the player, no trusted `blob:`/`data:` play src, license segments stay encrypted until decrypt, owner downloads unchanged (paid, watermarked).
- A failed play shows a short red line in the player bar instead of Safari’s raw error.

## Technical impact

- If `MediaSource.isTypeSupported('audio/mpeg')`, keep MSE (Chrome). The only `blob:` URL is a MediaSource handle, not an MP3 file.
- Otherwise decrypt CXA1 chunks, wipe the MP3 bytes after `decodeAudioData`, play PCM through `ProtectedAudioGraph` (no `audio.src` of a concatenated MP3).
- Packaged `package_status=ready` never falls through to `/play` or `/stream` after a license/MSE failure.
- `isTrustedPlayUrl` explicitly rejects `blob:` and `data:` (same denylist as the API theft tests).
- Hidden in-DOM `<audio playsInline>` + Web Audio unlock on tap for iOS silent autoplay. No silent MP3 data URI.
- Device id can fall back to `localStorage` if IndexedDB fails (Safari private mode). It is not an audio leak.

## Files touched

- `music_web/src/lib/mpeg-playback.ts`
- `music_web/src/components/player-provider.tsx`
- `music_web/src/components/player-bar.tsx`
- `music_web/src/lib/content-license.ts`
- `music_web/src/lib/streaming-api.ts`

## Migration / deploy

Sandbox `music_web` only. No API/migration. Production only on explicit request.

## Tests

- Existing `platform_api/tests/test_protected_playback_theft_vectors.py` still forbids origin URLs, `blob:`, `data:audio/mpeg`, download/lyrics as play src, and unclamped Range.
- Manual: iOS Safari Version 1 and Version 2 play with audible audio; DevTools should not show an `audio/mpeg` blob URL as `audio.src`.

## Follow-ups

- Production music_web after sandbox smoke.
- Leftover unpackaged Music MP3 encrypt still required so Version 1 is not plaintext on the clamped proxy.
