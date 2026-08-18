# Music web session refresh

**Date:** 2026-08-18  
**Surfaces:** music_web

## Summary

Music Streaming signed people out about every 15 minutes because the access cookie expired and the client never called `/auth/refresh`. The 7-day refresh cookie was already set; music web now uses it the same way the user portal does.

## Product impact

**Before:** After ~15 minutes, a reload or library/likes call returned 401 and the header showed signed out. Users had to log in again even though they had a valid refresh cookie.

**After:** Expired access cookies are silently renewed. Listeners stay signed in for up to 7 days of refresh-token lifetime (or until they sign out / change password).

## Technical impact

- New `musicAuthFetch` wrapper: on 401, `POST /api/v1/auth/refresh` with cookies, then retry once. Concurrent 401s share a single refresh.
- Login/register/refresh themselves do not trigger another refresh.
- Library likes, playlists, generate, and billing use the same wrapper.
- Auth bootstrap no longer treats network/5xx as a logout.

## Files touched

- `music_web/src/lib/auth-fetch.ts`
- `music_web/src/lib/auth-api.ts`
- `music_web/src/lib/library-api.ts`
- `music_web/src/lib/playlist-api.ts`
- `music_web/src/lib/web-music-api.ts`
- `music_web/src/lib/subscription-api.ts`
- `music_web/src/components/auth-provider.tsx`
- `music_web/CHANGELOG.md`

## Migration/deploy

No API or DB change. Sandbox already rebuilt. Production: file-scoped music_web rebuild after merge to `latest-web-music-main-branch`.

## Tests

- Sign in on sandbox music → wait past 15 minutes (or expire the access cookie) → reload: still signed in.
- Library likes still work after the access cookie expires.
- Sign out still clears the session.
- Wrong password on login still fails (no refresh loop).

## Follow-ups

- None.
