# Un-nest web-music billing onto `/api/v2`

**Date:** 2026-08-24  
**Branch:** `fix/api-v2-url-on-main`

## Summary

Web-music subscription, credit, and top-up routes were mounted under the global `/api/v1` prefix **and** used a `/v2/...` router prefix, so clients called `/api/v1/v2/subscriptions/purchase`. Canonical URLs are now `/api/v2/subscriptions`, `/api/v2/credits`, and `/api/v2/topups`. The old nested paths are rewritten at the edge so in-flight clients do not 404.

## Product impact

- Music web checkout, credit balance, and top-ups call `/api/v2/...`.
- Auth, streaming, generate, and desktop billing stay on `/api/v1`.
- Desktop `/api/v1/credits` is unchanged (different wallet).

## Technical impact

- `api_v2_prefix` is `/api/v2`. The three billing routers use resource prefixes only (`/subscriptions`, `/credits`, `/topups`).
- `LegacyNestedV2PathMiddleware` rewrites `/api/v1/v2/...` → `/api/v2/...` before routing.
- Rate-limit and audit path stripping understand both version prefixes and the legacy nest.
- CutLuy webhooks stay on `/api/v1` (already configured in CutLuy).
- Sandbox deploy is **file-scoped** so credits-only v3 mounts in `main.py` / `config.py` are not overwritten.

## Files touched

- `platform_api/config.py`
- `platform_api/http_paths.py`
- `platform_api/main.py`
- `platform_api/middleware/legacy_api_paths.py`
- `platform_api/middleware/rate_limit.py`
- `platform_api/middleware/audit.py`
- `platform_api/routers/v2_subscriptions.py`
- `platform_api/routers/v2_credits.py`
- `platform_api/routers/v2_topups.py`
- `platform_api/tests/test_api_v2_prefix.py`
- `platform_api/tests/test_rate_limit.py`
- `music_web/src/lib/subscription-api.ts`
- `scripts/deploy/smoke_web_music_credits_sandbox.py`
- `scripts/deploy/diag_purchase_500_sandbox.py`
- `platform_api/CHANGELOG.md`
- `music_web/CHANGELOG.md`

## Migration/deploy

No database migration. File-scoped sandbox hotfix of the URL files, then `music_web` rebuild of `subscription-api.ts` only. Production only on explicit request.

## Tests

- `python -m pytest platform_api/tests/test_api_v2_prefix.py platform_api/tests/test_rate_limit.py -q`
- After sandbox deploy: unauthenticated `GET /api/v2/credits/balance` and `GET /api/v1/v2/credits/balance` both 401; `GET /api/v2/subscriptions/plans` 200.

## Follow-ups

- Production API + music_web deploy when asked.
- Remove the `/api/v1/v2` rewrite after all clients have been on `/api/v2` long enough.
