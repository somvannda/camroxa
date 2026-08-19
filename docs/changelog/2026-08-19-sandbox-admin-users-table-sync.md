# Sandbox admin Users table: sync Tag / Free / used-total

**Date:** 2026-08-19  
**Surfaces:** `platform_api`, `admin_portal`  
**Branch:** `feature/admin-user-generated-songs`

## Summary

Sandbox admin Users still showed the old list (wallet `0 cr`, Plan **No plan**,
no Tag/Burned). Production admin already had Tag / used-total Credits / Burned
columns. The generated-songs sandbox hotfix rebuilt admin **without** uploading
`index.tsx`, so the list source stayed pre-Tag.

Sandbox API also lacked Music **Free** daily-pool enrichment (`_is_music_web_user`
+ `web_music_daily_usage`). Live production `users.py` had avatar/freeze extras
that git `main` does not, so we merged those instead of tarball-syncing API.

## Product impact

- Sandbox Users table matches production columns: Tag, Credits `used / 50`,
  Burned, Plan **Free** for Music-tagged accounts with no paid Music plan.
- User detail keeps freeze actions and the generated-songs panel.

## Technical impact

- File-scoped sandbox upload of merged `users.py` (production live file + Free
  inference + `admin_web_music_router`) and production `index.tsx`.
- No full `platform_api` tarball (would drop live `web_music.py` / avatars).
- Production not changed.

## Files touched

- `platform_api/routers/users.py` (merged; not git-main-only)
- `admin_portal/src/pages/users/index.tsx`
- `admin_portal/src/pages/users/user-detail.tsx`
- `admin_portal/src/hooks/use-users.ts`
- `admin_portal/src/types/models.ts`
- `scripts/deploy/hotfix_admin_users_table_sync_sandbox.py`
- `admin_portal/CHANGELOG.md`
- `platform_api/CHANGELOG.md`

## Migration/deploy

Sandbox only: `python scripts/deploy/hotfix_admin_users_table_sync_sandbox.py`

## Tests

- `pytest platform_api/tests/test_users_router.py platform_api/tests/test_admin_user_web_music.py`
- After deploy: hard-refresh `https://admin.sandbox.camxora.com` Users.

## Follow-ups

- Production `users.py` still needs the same Free-inference merge if Music free
  users should show `used / 50` there (UI columns already exist).
- Do not full-sync API from this worktree.
