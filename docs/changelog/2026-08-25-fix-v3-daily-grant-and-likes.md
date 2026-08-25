# Fix sandbox music 500s (daily_grant tag + streaming likes)

## Summary

Authenticated music web calls to `/api/v3/me/credits` and `/api/v3/web-music/quota` returned 500 because Free daily mint inserts `credit_wallet_lots.tag = 'daily_grant'`, which the DB check constraint did not allow.

`/api/v3/streaming/library/likes/ids` returned 500 because `wire_dependencies` passed `redis=` into `StreamingCatalogService`, which only accepts `pool`.

Admin marketplace preview `<img>` tags still requested `/api/v1/...` because the API hardcoded that prefix in `preview_url`.

## Fix

- Migration `117_daily_grant_lot_tag.py`: allow `daily_grant` + unique daily index.
- `wire_dependencies.py`: construct `StreamingCatalogService(pool)` only.
- Admin Plans credits-only table: null-safe `toLocaleString` for missing monthly/daily credits.
- Sandbox nginx: long-timeout stream/license locations match `/api/v1` and `/api/v3`.
- Startup migration runner skips auto-upgrade when DB revision is missing from local files (prevents hang → 502).
- Music sandbox rebuild rewrites remote-only `/api/v1` leftovers (studio/artist modules) to `/api/v3`.
- Marketplace `preview_url` now uses `/api/v3/...`; admin UI rewrites legacy `/api/v1` preview paths; missing preview files return 404 instead of 500.
- Admin credits-only Plans table reads `GET /api/v3/admin/plans` (full grant/visibility fields). `PlanResponse` also includes `monthly_credits` / `daily_credits` / `is_public` so `GET /api/v3/plans` is not silently empty for those columns.
- `GET /api/v3/subscriptions/plans` now SELECTs `daily_credits` (Free was returning `0` while DB had `50` — same incomplete-payload class as admin credits-only).