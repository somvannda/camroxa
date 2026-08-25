# Clients: API v3 only cutover (2026-08-25)

All Camxora client surfaces now call `/api/v3` exclusively. No client code
references `/api/v1` or `/api/v2` anymore.

## Surfaces updated

### camxora_python (desktop)
- Version bumped to **1.3.2** (`pyproject.toml` + `resources/app-version.txt`) for mandatory force-upgrade once Admin publishes a software-update release.
- `secure_storage.py` — `DEFAULT_API_BASE_URL` → `http://localhost:8000/api/v3`
- `bootstrap.py` — sandbox/production env shortcuts updated to `/api/v3`
- `.env.sandbox.example` / `.env.production.example` — `CAMXORA_API_BASE_URL` uses `/api/v3`
- `ws_url.py` — WebSocket helper builds `…/api/v3/ws`
- `api_health.py` — health-URL extractor strips `/api/v3` suffix
- `marketplace_view.py` — asset-URL deduplication and default base use `/api/v3`
- All test files asserting API base URLs updated to `/api/v3`

### music_web
- `subscription-api.ts` — `API_V2` constant renamed to `API_V3` (`/api/v3`); v1
  fallback removed from `fetchPublicPlanRows`
- All other `src/lib/` and `src/components/` files: `/api/v1` → `/api/v3`

### admin_portal
- `http-client.ts` — auth/refresh and admin 403-guard paths use `/api/v3`
- All `src/hooks/` files: `/api/v1` → `/api/v3`
- All `src/pages/` and `src/components/` files: `/api/v1` → `/api/v3`

### website
- `platform-api-base.ts` — dev and prod defaults use `/api/v3`
- `pricing/page.tsx`, `pricing/profile-addon-pricing.tsx`,
  `pricing/usage-rates-section.tsx` — hardcoded base URLs updated

### user_portal
- `platform-api.ts` — production and dev defaults use `/api/v3`
- `middleware.ts` — loopback API uses `/api/v3`
- `app/invite/page.tsx` — API base uses `/api/v3`

## Grep gate result
```
rg "/api/v1|/api/v2" camxora_python music_web/src admin_portal/src website/src user_portal/src
# → 0 matches ✓
```
