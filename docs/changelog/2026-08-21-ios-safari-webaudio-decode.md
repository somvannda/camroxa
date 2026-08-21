# iOS Safari packaged play: decode without MSE or MP3 blobs

**Date:** 2026-08-21  
**Branch:** `bugfix/ios-safari-playback`  
**Surfaces:** music_web

## Summary

After the first Safari fallback, iPhone still showed “This track could not start on this device” on Create (Velvet Crash). That string is our mapping of Safari’s “operation-specific reason”: either MSE `audio/mpeg` (iOS 17+ `MediaSource.isTypeSupported` can lie) or `decodeAudioData` rejecting MP3/ID3.

Safari/iOS now never uses MPEG MSE. Packaged audio is decrypted in memory, ID3 is stripped, native decode is tried, then mpg123 WASM decodes to PCM for Web Audio. No `blob:` / `data:` MP3 URL.

## Product impact

- iPhone Safari should play packaged Create/catalog tracks with sound.
- Protection unchanged: no Suno/B2 URLs, no downloadable MP3 object URL, license chunks stay encrypted until decrypt.

## Technical impact

- `shouldUseMpegMediaSource()` is false on Apple WebKit even if `isTypeSupported('audio/mpeg')` is true.
- License `ready` (not stale `package_status` on the clip) chooses the packaged path.
- Incomplete chunk fetches no longer decode a truncated MP3.
- `mpg123-decoder` is a client-only fallback after native `decodeAudioData` fails.

## Files touched

- `music_web/src/lib/mpeg-playback.ts`
- `music_web/src/lib/mpeg-sync.ts`
- `music_web/src/lib/mp3-software-decode.ts`
- `music_web/src/components/player-provider.tsx`
- `music_web/src/lib/content-license.ts`
- `music_web/next.config.ts`
- `music_web/package.json`

## Migration / deploy

Sandbox file-scoped music_web hotfix (not a full tarball). Production only on explicit request.

## Tests

- Manual: iPhone Safari Create Version 1 and Version 2 play with audible audio.
- DevTools: `audio.src` is not `blob:audio/mpeg` or `data:audio/mpeg`.
