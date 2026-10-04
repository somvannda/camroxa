# musicapi: expose the window budget + concurrent-job cap in the admin console

## Summary

The pool-protection change (#237) added `requests_per_window` and
`max_concurrent_jobs` to the per-user `rate_limits` API, but the admin console's
"Rate limits" dialog could only read/write `requests_per_minute` and
`requests_per_day`. Operators had to fall back to `curl` to set the two new
limits. This surfaces them in the existing dialog.

## Product impact

- The admin **Users → Limits** dialog now edits all four per-user limits:
  - **Requests per Ns window** (N = the server's `RATE_LIMIT_USER_WINDOW_MS`,
    default 10s) — the sunoapi.org 20 req/10s shape.
  - Requests per minute, requests per day (unchanged).
  - **Max concurrent jobs** — falls back to the pool default when empty.
- Empty fields still mean "no limit" (or, for concurrent jobs, the pool default),
  and saving all-empty clears the user's row, exactly as before.

## Technical impact

- `web-admin/app/admin/users/page.tsx` (client component, no Next.js API surface
  changes):
  - Reads `requests_per_window`, `max_concurrent_jobs`, and `window_ms` from
    `GET /admin/users/:id/rate-limits`; the window label is rendered from
    `window_ms` so it tracks the server config instead of hardcoding 10.
  - Sends all four fields on `PUT /admin/users/:id/rate-limits`.
- No API, schema, or migration change — the backend already accepted both fields.

## Files touched

- `musicapi/web-admin/app/admin/users/page.tsx`
- `docs/changelog/2026-10-04-musicapi-admin-rate-limit-ui.md` (this file)

## Migration / deploy

- No migration. Deploy the `musicapi` stack as usual (the sync rebuilds
  `web-admin`). Backend `0025` must already be applied (it is, on sandbox and
  production).

## Tests

- `npm run build` in `musicapi/web-admin` → TypeScript clean, all static pages
  generated.
- Backend contract verified earlier (GET returns `window_ms` +
  `default_max_concurrent_jobs`; PUT persists all four fields).

## Follow-ups

- Optional: show a user's current in-flight job count next to the cap, sourced
  from `/metrics`.
- Bound the gate's waiting queue (unchanged follow-up from #237).
