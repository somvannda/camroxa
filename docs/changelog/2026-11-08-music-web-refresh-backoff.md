# music_web stops refreshing auth on every signed-out poll

**Date:** 2026-11-08
**Surface:** `music_web` (`music.camxora.com`)
**Branch:** `fix/web-auth-refresh-loop`

## Summary

While signed out, `music.camxora.com/create` kept polling license/credit
endpoints every few seconds. Each `401` went through `musicAuthFetch`, which
called `POST /api/v3/auth/refresh`; with no refresh cookie that also returned
`401`, and the cycle repeated — **1 909 browser `401`s to `/auth/refresh` today
alone**, versus 56 successful refreshes. The desktop audit flagged the same
pattern as the second-largest source of auth traffic.

## Product impact

- Signed-out visitors no longer generate a refresh call on every poll.
- A real sign-in is still picked up immediately: only a **rejected** refresh
  (`401`/`403`) is remembered, for 60 seconds. A network failure is not cached.
- Signed-in users are unchanged: one refresh, then the original request retries.

## Technical impact

- `music_web/src/lib/auth-fetch.ts`
  - `refreshAccessCookie()` now returns early for 60s after the server rejects a
    refresh (`REFRESH_REJECT_BACKOFF_MS`), instead of attempting one per 401.
  - Successful refresh clears the block; transport errors do not set it.
  - Exported `resetAuthRefreshState()` for tests.
- `music_web/src/lib/auth-fetch.test.ts` (new): 4 tests — rejected refresh is
  attempted once across two polls, successful refresh retries the request,
  network failure still retries next time, and the refresh endpoint never
  refreshes itself.

## Files touched

| File | Change |
|---|---|
| `music_web/src/lib/auth-fetch.ts` | 60s negative cache for rejected refreshes |
| `music_web/src/lib/auth-fetch.test.ts` | New tests |
| `music_web/CHANGELOG.md` | Entry |

## Migration/deploy

No schema or API change. `music_web` rebuild only.

## Tests

```bash
cd music_web
node --experimental-strip-types --test "src/lib/auth-fetch.test.ts"   # 4 passed
node --experimental-strip-types --test "src/lib/*.test.ts"            # 67 passed
```

## Follow-ups

- The license `client-trace`/`heartbeat` endpoints are still called while
  signed out; the client should stop its trace loop on the first `401` instead
  of relying on the server. Server-side, `client-trace` could answer `204` for
  anonymous callers instead of `401`.
