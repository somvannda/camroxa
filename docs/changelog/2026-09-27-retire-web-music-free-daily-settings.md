# Retire the legacy web-music free-daily settings

**Date:** 2026-09-27
**Branch:** `fix/legacy-web-music-free-daily-settings`
**Surfaces:** platform_api, admin_portal
**Status:** implemented

## Summary

The credits-only unification moved the free Music allowance onto a real **Free**
plan row (`plans.daily_credits`), but two `system_settings` rows still shadowed
it: `web_music_free_daily_limit` (Alembic 084, `5`) and
`web_music_free_daily_credits` (Alembic 095, `50`). `CreditService.daily_free_limit()`
read the plan row first and silently fell back to the setting, so a Free row
edit and the setting could disagree — and the setting could keep free daily
credits alive after the plan row was hidden or deactivated.

Both settings are retired. The active Free plan row is now the only source of
truth, and a missing or unparseable `daily_credits` means **0** free daily
credits rather than a hidden default.

## Product impact

- Editing the **Free** plan row in Admin → Plans is now the single place that
  changes the free daily allowance; nothing can override it.
- If the Free row is deactivated or removed, free users get no daily grant.
  Paid plans and paid users are unaffected.

## Technical impact

- `platform_api/models/products.py`: dropped `WEB_MUSIC_FREE_DAILY_LIMIT_KEY` /
  `_DEFAULT` (no consumers) and `WEB_MUSIC_FREE_DAILY_CREDITS_KEY` / `_DEFAULT`.
- `platform_api/routers/users.py`: dropped the duplicate `_KEY` / `_DEFAULT`
  constants and the unreferenced helpers `_free_music_credit_fields()` and
  `_web_music_daily_free_limit()`.
- `platform_api/services/v2/credit_service.py`: `daily_free_limit()` keeps the
  active-Free-plan read and returns `0` when the row or its `daily_credits` is
  missing; the `system_settings` fallback and its imports are gone.
- `admin_portal/src/pages/plans/music-web-free-credits-section.tsx`: deleted.
  The component had been unmounted since the credits-only recast, so it only
  offered a dead way to edit the retired setting. The Settings → Music Web note
  that points at the Free row is unchanged.
- Alembic `123_retire_web_music_free_daily_settings` deletes any residual rows
  for both keys; `downgrade()` re-inserts `5` / `50`.

## Files touched

- `platform_api/models/products.py`
- `platform_api/routers/users.py`
- `platform_api/services/v2/credit_service.py`
- `platform_api/migrations/versions/123_retire_web_music_free_daily_settings.py` (new)
- `admin_portal/src/pages/plans/music-web-free-credits-section.tsx` (deleted)

## Migration / deploy

- Run Alembic to `123_retire_web_music_free_daily_settings` (idempotent `DELETE`
  of the two keys) and rebuild `admin_portal`. Sandbox first.
- Sandbox already had `web_music_free_daily_credits` deleted by the credits-only
  cutover test, and `daily_free_limit()` returned the plan value, so `123` is a
  no-op there.

## Tests

- `platform_api/tests/test_web_music_credit_hardening.py` (covers
  `consume_credits` / daily fallback; `daily_free_limit` is patched, so the
  removed fallback does not change these cases).

## Follow-ups

- None.
