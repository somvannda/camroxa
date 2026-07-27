# Music-native auth session + profile/library shell

**Date:** 2026-07-27  
**Status:** implemented; sandbox live

## Summary

Listeners now sign in on Music Streaming itself (same Camxora account). Session cookies are set via `music.*/api` so returning from the user portal is no longer required. Music `/library` and `/profile` stay on music_web; portal login accepts `return_to` back to music as a fallback.

## Product impact

**Before:** Sign in from music opened the user portal; after login users landed on dashboard/onboarding and music still looked logged out (cookies on `app.*` only).

**After:** Sign in / Sign up on music keep the user on music. Header shows display name + Sign out. Library and profile pages exist on music (playlist CRUD still Phase 5). Portal `?return_to=https://music...` redirects back when used.

## Technical impact

- `music_web`: AuthProvider, `/login`, `/register`, `/library`, `/profile`; browser API calls use same-origin `/api` with credentials.
- `platform_api`: `/auth/logout` accepts cookie auth (not Bearer-only).
- `user_portal`: `resolveExternalReturnTo` allowlist for music hosts.

## Files touched

- music_web: auth-api, auth-provider, login/register/library/profile pages, header/sidebar/layout, streaming-api base URL
- platform_api: `routers/auth.py` logout
- user_portal: `return-to.ts`, login form/page
- docs: enhancement Phase 2, this changelog

## Migration / deploy

```bash
python scripts/deploy/sync_platform_api_sandbox.py
python scripts/deploy/rebuild_music_web_sandbox.py
python scripts/deploy/rebuild_user_portal.py   # if script targets sandbox via resolve_sandbox_ssh
```

No DB migration.

## Tests

- Sandbox: open music → Sign in → stay on music; refresh stays signed in; Profile/Library visible; Sign out clears session.

## Follow-ups

- Gate `play-url` behind auth.
- Playlist/likes APIs (Phase 5).
- Optional parent-domain cookie SSO so portal ↔ music share one cookie without music-native login.
