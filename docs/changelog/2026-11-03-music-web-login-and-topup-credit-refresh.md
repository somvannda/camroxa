# Music Web: sign-in and top-up credit refresh

**Date:** 2026-11-03
**Surfaces:** `music_web` (music.camxora.com), `platform_api`

## Summary

Two reports shared the same generic symptom — `An unexpected error occurred.` — and the same
underlying design flaw: one failing background request was allowed to cancel everything else.

1. **After sign-in** some accounts showed an error even though the session was valid. The login
   form treated a failed `GET /api/v3/users/me` (a 5xx) as a failed sign-in, so a successful
   login rendered an error banner.
2. **After a successful top-up** the payment modal flipped to "Payment successful" but the Create
   page credit chip never updated and the page showed an error. `refreshList()` ran the quota,
   generation list, workspace list and credit balance in one `Promise.all`; the first rejection
   aborted the rest, so `setCreditBalance()` never ran and the raw server message leaked into
   `createError`.

## Product impact

- Signing in no longer fails visually because an unrelated read failed; the user lands on their
  destination page with a valid session.
- Credits bought in the checkout modal now appear on `/create` (and in the header/sidebar chip)
  as soon as CutLuy reports fulfilment, even if another panel request fails.
- A background refresh failure shows an actionable message
  ("Could not refresh the studio just now. Your credits are safe — try again in a moment.")
  instead of `An unexpected error occurred.`
- The credit chip keeps its last known value on a failed refresh instead of dropping to 0.

## Technical impact

`music_web`

- `app/login/page.tsx`: the post-login profile read is now best-effort (`catch → null`). Only
  `login()` failures show an error; the profile is only used for the verify-email redirect.
- `components/create-page-client.tsx`:
  - `refreshList()` uses `Promise.allSettled` and applies each result independently, credits
    first, then re-throws the first real failure so the caller can show one message.
  - new `describeRefreshError()` maps a 5xx / generic message to an actionable hint.
- `components/credit-header.tsx`: keeps the previous balance when a refresh returns null.
- `components/auth-provider.tsx`: listens for `camxora:credits-updated` and refreshes the session
  view, so plan/credit chrome agrees with the wallet after a purchase.

`platform_api`

- `routers/users.py`: `GET /users/me` enrichment (wallet, profile count, entitlement, avatar) is
  now non-fatal and logs the user id. `_user_to_response` coerces `display_name`, `email`,
  `created_at` and `products` (text[], JSON string, JSON object) so a dirty row cannot fail
  response validation.
- `routers/web_music.py`: `GET /web-music/quota` logs the account on failure and rounds every
  integer counter (`limit`, `used`, `remaining`, `credits_remaining`, `credits_per_song`,
  `queue_*`, `daily_free_*`) via `_coerce_quota_payload`, so a fractional balance cannot trip
  Pydantic's `int` validation (same failure class as the earlier `wallet_balance` regression).

## Files touched

- `music_web/src/app/login/page.tsx`
- `music_web/src/components/create-page-client.tsx`
- `music_web/src/components/credit-header.tsx`
- `music_web/src/components/auth-provider.tsx`
- `platform_api/routers/users.py`
- `platform_api/routers/web_music.py`
- `platform_api/tests/test_login_and_quota_resilience.py`

## Migration / deploy

No schema change. Deploy `platform_api` and `music_web` together (the client change is what
actually recovers the credit display; the API change removes the 500s behind it).

## Tests

- `python -m pytest platform_api/tests/test_login_and_quota_resilience.py` — 6 new tests covering
  product-shape coercion, blank `display_name`, missing `created_at`, fractional/unparseable quota
  counters and payload immutability.
- `python -m pytest platform_api/tests -k "web_music or quota or users or credits"` — 250 passed.
- `npm test` (music_web) — 57 passed.
- `npx tsc --noEmit` — no new errors (the pre-existing `TS5097` errors in `src/lib/*.test.ts` are
  unchanged).

## Follow-ups

- Pull the production traceback for the affected account
  (`journalctl -u camxora-api | grep "web-music /quota failed"` / `"GET /users/me"`) to name the
  exact failing query. The new log lines include the user id for that purpose.
- Consider returning a friendlier `message` than `An unexpected error occurred.` from the global
  exception handler, or a correlation id the user can quote to support.
