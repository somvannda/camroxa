# Admin users page — search and filters

## Summary

Admins can now find an account from the Users page instead of paging through the full list: a free-text search (email / display name / user ID) plus filters for role, email-verified state, plan (or Free), status, and registration date range. All filtering runs server-side so it stays correct with pagination.

## Product impact

- Search a user by email, display name, or user ID.
- Filter by role (user / admin), email verified (verified / pending), plan (each catalog plan, or **Free** = no active plan), status, and registration date range.
- Filters use an explicit **Apply** / **Clear** panel, so the list does not refetch on every keystroke.
- The registration-date filter now works. Previously the UI sent `from_date` / `to_date` while the API expects `date_from` / `date_to`, so FastAPI silently ignored the unknown params and the date filter had no effect.

## Technical impact

- `GET /api/v3/users` gains `search`, `role`, `email_confirmed`, `plan_name`, and `is_free` query params (alongside the existing `status`, `date_from`, `date_to`).
- Search uses `ILIKE` over `email`, `display_name`, and `id::text`.
- Plan filtering uses `EXISTS` subqueries over active `licenses` **and** active `web_subscriptions`, so both entitlement paths are covered; `is_free` is the negation of both.
- Count is now `COUNT(*)` and the data query a plain `SELECT` (the previous `licenses` INNER JOIN + `DISTINCT` is removed), so page totals are exact and the query plan stays simple.
- The frontend `UserListParams` date fields are renamed to `date_from` / `date_to` to match the API.

## Files touched

- `admin_portal/src/pages/users/index.tsx`
- `admin_portal/src/types/api.ts`
- `platform_api/repositories/user_repo.py`
- `platform_api/services/user_service.py`
- `platform_api/routers/users.py`
- `platform_api/tests/test_user_service.py`

## Migration / deploy

- Deploy **platform_api** and **admin_portal** to sandbox, smoke-check, then production.
- No DB migration.
- No new index added; `ILIKE '%...%'` searches are unanchored and will not use a b-tree index. Acceptable at current user volume — revisit with a trigram index if the users table grows large.

## Tests

- `platform_api`: `pytest tests/test_user_service.py tests/test_users_router.py` — 31 passed (service fake repository updated to the new signature; in-memory role/search filtering added).
- `admin_portal`: `npm run build` (tsc + vite) — passes.
- Manual: apply each filter and confirm the count/rows match; confirm Clear resets to the unfiltered list.

## Follow-ups

- Consider a `pg_trgm` GIN index on `users.email` / `display_name` if search latency becomes noticeable.
- Column sorting in the admin `DataTable` is visual-only (it never reorders `data`); could be wired to server-side `order_by` in a separate change.
