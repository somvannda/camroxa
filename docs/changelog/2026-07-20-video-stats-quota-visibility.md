# Video stats split + clearer plan limits on dashboards

**Date:** 2026-07-20  
**Status:** implemented (sandbox API + user portal deployed; desktop build for local verify)

## Summary

Studio exports, manual exports, and YouTube uploads are counted separately (one shared track-export quota pool for studio + manual). User portal and desktop dashboards now show remaining plan limits as easy **X / Y** (month + today). Export billing refunds **technical failures** and **never-started** tracks on user stop; completed and in-progress work is kept.

## Product impact

**Before**
- Dashboard “videos” mixed meanings; remaining limits were buried or shown as bare remaining counts.
- Manual exports often did not consume or refund quota clearly.
- Historical manual exports before this change were not counted.

**After**
- Portal Overview opens with **Your limits**: Suno, images, drafts, track exports, merges (month), plus track exports/merges **today**, and a per-channel daily preview.
- Desktop **Remaining This Month** shows progress bars plus **X of Y left**, and account-level **today** caps for track exports and merges.
- 7-day charts split studio / manual / YouTube (portal + desktop).
- **Refund policy:** technical fail → refund undelivered tracks; user Stop → keep completed + in-progress, refund only never-started; user-cancelled merge keeps charge.

## Technical impact

- API: `video_manual` consume/refund; dashboard stats expose `studio_exports`, `manual_exports`, `youtube_uploads` and daily usage breakdown.
- Desktop: manual/studio billing with the refund policy above; dashboard quota UX.
- User portal: overview limits panel; credits panel daily video/merge rows; chart series split.
- Website marketing counters: not updated (no public counter UI); deferred.
- Website Terms §5 and Support Help Center: payment cancel/renewal unchanged; export usage restore policy documented (technical fail vs user stop).
- Video-page button renamed **Manual Export**; Studio = Progress/pipeline only.
- `video_export_telemetry` table + `POST /generation/video/telemetry`; admin Usage shows export timing; portal shows 7-day avg studio/manual export seconds.

## Historical data gaps (item 3)

| Period | Studio exports | Manual exports | YouTube uploads |
|--------|----------------|----------------|-----------------|
| Before this change | Counted as `video` usage when pipeline billed | Often **uncounted** (no consume) | Successful `youtube_upload_jobs` only |
| After deploy | `usage_tracking` op `video` | `usage_tracking` op `video_manual` | Same job successes |

Users should expect older manual work to under-count until new exports land. Support copy: “Track export totals start when billing is deployed; older manual renders may not appear.”

## Files touched

### Platform API
- `platform_api/routers/generation.py`, `stats.py`, `credits.py`
- `platform_api/services/billing_mode_service.py`, `usage_enforcement_service.py`, `quota_display_service.py`
- `platform_api/models/schemas.py`, `local_platform_operations.py`

### Desktop (`camxora_python`)
- `features/video/views/video_view.py` (billing + refunds)
- `features/dashboard/widgets/remaining_month_card.py`
- `features/dashboard/widgets/daily_channel_quota_card.py`
- `features/dashboard/widgets/weekly_usage_card.py`
- `shared/widgets/usage_chart.py`
- `shared/models/platform.py`

### User portal
- `user_portal/src/app/dashboard/page.tsx`
- `user_portal/src/app/dashboard/credits/credits-panel.tsx`
- `user_portal/src/components/dashboard/usage-curve-chart.tsx`
- `user_portal/src/lib/stats.ts`, `quota.ts`

### Admin / Electron (earlier in set)
- Admin credits labels; Electron Home/Profile KPI labels as applicable

## Migration / deploy

1. Deploy `platform_api` + `user_portal` to sandbox (`python scripts/deploy/deploy.py` or sync scripts).
2. No DB migration required for ops keys (usage_tracking string keys).
3. Desktop build needed for refund + remaining-card UX; portal-only verify works for limits UI against new API.
4. Smoke: open portal Overview → confirm X/Y limits; run/stop a manual export → remaining should restore unused units.

## Tests

- Existing `test_stats_router`, `test_video_merge_billing` (prior set).
- Manual sandbox verification by user after deploy.

## Follow-ups

- Website public marketing stats (if product wants public totals).
- Electron HomePage remaining card still thin vs PySide dashboard (optional parity).
- Alerting when refund API fails silently (client currently swallows refund errors).

## Chart performance (2026-07-20)

**Problem:** Qt Charts (`QSplineSeries` + series animations + live `QChartView`) made the dashboard scroll area feel sticky and slowed the whole desktop shell.

**Fix:** replace with a custom QPainter soft-curve chart + DPI-aware pixmap cache; skip chart/day-grid rebuild when usage fingerprint is unchanged; remove `PySide6.QtCharts` from the PyInstaller hiddenimports.

**Files:** `camxora_python/shared/widgets/usage_chart.py`, `features/dashboard/widgets/weekly_usage_card.py`, `Camxora.spec`, root `CHANGELOG.md`.

## Weekly chart hid today’s Manual exports (2026-07-20)

**Incident:** Desktop/portal weekly usage showed Manual exports `(0)` while Studio had volume. Sandbox DB for `somvannda@gmail.com` already had `video_manual` rows dated **2026-07-20**, but the stats window used `today-7 .. today-1` (e.g. Jul 13–19), so same-day Manual never appeared.

**Fix:** inclusive 7-day window `today-6 .. today` in `platform_api/routers/stats.py`. Deploy API; hard-refresh portal / restart desktop dashboard.

**Verification:** after deploy, weekly chart last column is today; Manual legend/line reflects today’s `video_manual` SUM.

## Support note — 2026-07-20 desktop `POST /generation/video/consume` 422

**Not a product bug.** During GPU-export performance testing, the Camxora log showed:

```text
POST /generation/video/consume → 422: operation_type must be 'video' or 'video_merge'.
Manual export blocked (billing): …
```

**Root cause (operator):** the test account had **run out of video/export quota**. Quota was increased and exports resumed.

**Do not** treat this log line as a broken `operation_type` contract or a desktop billing regression unless reproduceable with remaining quota. Manual export correctly sends `video_manual` (accepted by current API); a depleted plan/wallet also surfaces as a blocked consume and can look like a validation failure in the UI log.

**Verification after quota top-up:** manual export starts again; no code change required for this incident.
