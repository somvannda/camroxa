# Admin: Music Web free daily credits setting

**Date:** 2026-08-18  
**Surfaces:** `admin_portal`  
**Branch:** `feature/admin-music-free-daily-credits-setting`

## Summary

Camxora Music free users already get a **credit** pool (default 50 credits/day,
10 credits per song ≈ 5 songs), not a separate song-count cap. Style and lyrics
assist spend from the same pool. There was no dedicated admin control — only the
raw `system_settings.web_music_free_daily_credits` key.

Admin **Plans** and **Settings → Music Web** now let operators set that daily
credit number, with a live song equivalent and presets (1 / 3 / 5 songs, or 0
listen-only).

## Product impact

- Changing 50 → 30 credits limits unpaid Music Web users to ≈ 3 songs/day.
- Changing to 0 blocks free generations until they subscribe.
- Paid Music subscribers are unchanged (monthly plan credits).
- Desktop Studio plans are unchanged.
- Admin Users already shows remaining / this limit for Free Music rows.

## Technical impact

- Writes `system_settings.web_music_free_daily_credits` (`integer`).
- Default remains 50 when the key is absent.
- Generation already meters this pool via `web_music_daily_usage`; this change
  is the admin UI for the existing key.

## Files touched

- `admin_portal/src/pages/plans/music-web-free-credits-section.tsx`
- `admin_portal/src/pages/plans/index.tsx`
- `admin_portal/src/pages/settings/index.tsx`
- `admin_portal/CHANGELOG.md`
- `docs/changelog/2026-08-18-admin-music-free-daily-credits-setting.md`

## Migration / deploy

No migration. File-scoped sandbox admin sync + rebuild. Production only on
request. After save, new generations use the new cap immediately; today's
already-used credits still count against the new limit.

## Tests

- Load Plans: card shows 50 (or the saved value) and "≈ 5 songs/day".
- Click **3 songs (30 cr)** → Save → toast shows ≈ 3 songs/day.
- Settings → Music Web shows the same saved value.
- Reset to 50 restores the default (deletes the override row).

## Follow-ups

- Music Web pricing page still hardcodes 50 daily credits in marketing copy.
  Wire that from the same setting when the public plans API can return it.
