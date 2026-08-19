# Camxora Music — Suno-like Create + Stream (Phase 1)

**Date:** 2026-08-15  
**Surfaces:** `platform_api`, `music_web`, `user_portal`  
**Branch:** `feature/music-web-suno-create-shell`

## Summary

`music.camxora.com` (and sandbox / local `:3003`) is now a Camxora-branded
create + stream product: marketing home for guests, login-gated Create with
two clips + MP3, and Explore as a restyled published catalog. Music signup is
tagged `music_web` on the same email/password identity and skips studio
invite-only plus dual OK/ALT channel onboarding.

Web generation uses a new `/api/v1/web-music` API (auth only — no desktop
license or channel profile). Jobs are stored as `suno_tasks.source =
web_music` and never auto-publish to the public streaming catalog.

## Product impact

- Guests see a marketing home (“Make any song you can imagine”) with Create /
  Join CTAs. Logged-in users get the app shell: Home / Explore / Create plus
  the bottom player.
- Music register has no invitation-code field and lands on `/create`.
- Create (Simple/Advanced) submits lyrics or a description to the same
  sunoapi.org generate path the desktop app uses (`SunoClient` + key pool +
  callback). Two versions play in the player bar; MP3 download is proxied.
  **5 free songs**, then Create requires Upgrade to Pro (active desktop
  license counts as Pro). Explore is login-gated (`/login?next=/explore`).
- Sidebar stubs (Invite friends, Upgrade to Pro) and Create stubs (`+ Audio` /
  `+ Voice` / `+ Inspo`, More Options, WAV, Save to workspace) are visible
  but not wired.

## Technical impact

- `users.products TEXT[]` (existing users backfilled to `['studio']`).
  `POST /auth/register` accepts `product` / `X-Signup-Product`. Music web
  always sends `music_web`; user portal sends `studio`. Completing channel
  onboarding adds `studio` if missing.
- `GET /users/me` returns `products`.
- New router `/api/v1/web-music`: quota, generate, list/status, MP3
  download/stream proxy. Lifetime free cap (default 5) in
  `web_music_daily_usage` / `web_music_free_daily_limit`. Pending Create jobs
  poll sunoapi.org record-info so clips appear without waiting only on the
  callback. Active desktop license skips the free cap (Pro).
- Suno callbacks skip catalog upload when `source = web_music` or there is no
  `song_id`.
- Simple mode: lyrics helper then custom generate (one generate path).

## Files touched

- `platform_api/migrations/versions/084_user_products_web_music.py`
- `platform_api/models/products.py`, `platform_api/models/domain.py`
- `platform_api/routers/auth.py`, `users.py`, `web_music.py`, `callbacks.py`,
  `channel_setup.py`
- `platform_api/services/web_music_service.py`, `generation_service.py`,
  `streaming_upload_service.py`
- `platform_api/repositories/user_repo.py`, `batch_repo.py`
- `platform_api/main.py`, `wire_dependencies.py`
- `platform_api/tests/test_auth_router.py`, `test_web_music_router.py`
- `music_web/src/app/{create,explore}/`, `page.tsx`, `layout.tsx`,
  `login/page.tsx`, `register/page.tsx`
- `music_web/src/components/{shell-switcher,home-gate,sidebar,create-page-client,explore-page-client,player-provider}.tsx`
- `music_web/src/lib/{auth-api,web-music-api,streaming-api}.ts`
- `user_portal/src/lib/platform-api.ts`
- `platform_api/CHANGELOG.md`, `music_web/CHANGELOG.md`,
  `user_portal/CHANGELOG.md`

## Migration / deploy

1. `python scripts/deploy/sync_platform_api_sandbox.py`
2. `python scripts/deploy/run_alembic_upgrade_sandbox.py` (revision `084`)
3. `python scripts/deploy/rebuild_music_web_sandbox.py`

Smoke: `https://music.sandbox.camxora.com` — guest home, Create redirects to
login, after music signup two clips can generate under the free cap, Explore
still plays catalog, a web job does not appear as a new public album.

Production is not included.

## Tests

- `pytest platform_api/tests/test_web_music_router.py -q`
- `pytest platform_api/tests/test_auth_router.py -q` (logout fixture still
  needs middleware configure; register music_web cases pass)

## Follow-ups

Phase 2: WAV, private workspace persistence, +Audio/+Voice/+Inspo, More
Options, richer Explore. Phase 3: dual music-web vs desktop billing plans and
user invite-friends.
