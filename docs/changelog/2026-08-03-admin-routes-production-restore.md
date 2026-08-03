# Admin routes production restore

**Date:** 2026-08-03  
**Status:** implemented  
**Branch:** `fix/admin-routes-production-restore`

## Problem

Admin UI features that previously worked on production started failing:

- `GET /api/v1/admin/pipeline/board` → **404** (`admin_pipeline` file on disk but not registered in `main.py` / `wire_dependencies.py`)
- `GET /api/v1/admin/job-queue/metrics` → **500** (`admin.py` called `get_job_queue_repo` but production `dependencies.py` lacked that provider)
- `GET/POST /api/v1/users/{id}/fail-absorb` → **404** (admin UI present; API routes never shipped)
- Provider key balances route returned keys but every balance fetch failed:
  `KeyPoolService` had no `get_decrypted_key_value` (balance service could not decrypt keys)

## Fix

Path-scoped restore of:

- `main.py` + `wire_dependencies.py` — register/wire `admin_pipeline`
- `dependencies.py` — `get_job_queue_repo` (+ provider balance service provider)
- `users.py` + `usage_enforcement_service.py` — fail-absorb status/reset admin APIs
- `key_pool_service.py` — add `get_decrypted_key_value` for admin balance lookups
- pipeline / job-queue / provider-balance supporting modules

## Deploy

`python scripts/deploy/hotfix_admin_routes_restore.py both`
