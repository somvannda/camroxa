# Admin provider today usage (balance drop)

## Summary

Provider credit cards show **today used / remaining** (e.g. `120 / 5,289.1`) where today used is the **balance drop** since a UTC day-start snapshot stored in Redis.

## Product impact

- Admins can see how much each provider burned today without leaving the dashboard.
- Used amount is red; remaining stays green.
- Top-ups during the day shift the baseline so prior usage is preserved.

## Technical impact

- `ProviderKeyBalanceService` writes `provider_key_balance_day:{provider}:{key_id}:{YYYY-MM-DD}` with start/last.
- API items include `used_today` and `day_start_balance`.
- First reading of the day sets used=0 (baseline = current remaining).

## Files touched

- `platform_api/services/provider_key_balance_service.py`
- `platform_api/routers/admin.py`
- `platform_api/tests/test_provider_key_balance_service.py`
- `admin_portal/src/types/provider-balances.ts`
- `admin_portal/src/components/dashboard/provider-key-balances-panel.tsx`

## Migration / deploy

- Deploy **platform_api** + **admin_portal** (sandbox first).
- No DB migration (Redis only).

## Tests

- Unit tests for `compute_day_usage` (first read, drop, top-up).

## Follow-ups

- Optional: show used on key rows only when > 0 to reduce noise on quiet days.
