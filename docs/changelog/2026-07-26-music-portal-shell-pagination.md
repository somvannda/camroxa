# Music portal Phase 0–1: pagination + branded shell

**Date:** 2026-07-26  
**Status:** implemented; sandbox live

## Summary

Started the music streaming portal enhancement: documented the full roadmap (shared Camxora auth, Spotify-like IA, lyrics, library), then shipped Phase 0 pagination totals and Phase 1 branded chrome (logo, purple tokens, header/footer, library CTA, discovery rail, albums/artists indexes).

## Product impact

**Before**
- Cyan utility UI, Disc3 “logo”, no header/footer, stub albums/artists pages, silent 24-item caps.

**After**
- Camxora logo + marketing-aligned purple theme, header search + Sign in/up, footer, Your Library empty state, right discovery rail, paginated albums/artists/search with Show more.
- Spec locked: same user portal auth; browse public; listen gated in Phase 2.

## Technical impact

- API: `GET .../albums|artists|search` return `{ items, total, limit, offset }` (search gains `offset`).
- `music_web`: shell components, Inter/Outfit, `public/camxora-logo.svg`, `/artists/[id]`.
- Deploy: `resolve_sandbox_ssh()` so sandbox_* scripts use `SANDBOX_VPS_HOST` (`46.250.235.83`), not production `VPS_HOST`.

## Files touched

- Docs: `docs/MUSIC_STREAMING_PORTAL_ENHANCEMENT.md`, `docs/MUSIC_STREAMING.md`, `docs/PRODUCT_SCOPE.md`
- API: `streaming_repo.py`, `streaming_catalog_service.py`, `streaming_public.py`, tests
- music_web: layout/header/footer/sidebar/player, catalog browsers, search client, globals, logo
- Deploy: `scripts/deploy/deploy.py` (`resolve_sandbox_ssh`), `sync_platform_api_sandbox.py`, `rebuild_music_web_sandbox.py`
- Rule: `.cursor/rules/sandbox-first-deploy.mdc`

## Migration / deploy

1. Deploy `platform_api` (pagination response shape is additive).
2. Rebuild/redeploy `music_web`.
3. Set `NEXT_PUBLIC_USER_PORTAL_URL` / `NEXT_PUBLIC_WEBSITE_URL` on music host if not already.

**Sandbox (2026-07-26):** `sync_platform_api_sandbox.py` + `rebuild_music_web_sandbox.py` against `SANDBOX_VPS_HOST=46.250.235.83`.

- API: `https://api.sandbox.camxora.com/.../albums` → `{ items, total, limit, offset }` (`total=77`).
- Music: `https://music.sandbox.camxora.com` → Camxora logo, Sign in/up, Your Library.

## Incident

Earlier sandbox scripts used `VPS_HOST`, which pointed at **production** (`82.197.71.248`) while public sandbox DNS is `46.250.235.83`. That briefly enabled `camxora-sandbox` nginx on production (missing LE certs → `nginx -t` failed). Fixed by removing the production symlink and reloading nginx; corrected scripts to `resolve_sandbox_ssh()`. Pagination code had already landed on production API as a side effect (additive/backward compatible).

## Tests

- `pytest platform_api/tests/test_streaming_catalog_repo.py`
- Sandbox smoke: albums keys + music HTML brand markers

## Follow-ups

- Phase 2: auth gate on `play-url` + session on music_web.
- Phase 3–5: richer album/artist heroes, synced lyrics rail, playlists.
- Audit remaining `*_sandbox.py` scripts that still hardcode `secrets["VPS_HOST"]`.
