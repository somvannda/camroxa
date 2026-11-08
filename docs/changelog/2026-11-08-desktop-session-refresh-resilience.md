# Desktop signs out on transient session-refresh failures ("Unauthenticated")

**Date:** 2026-11-08
**Surface:** `camxora_python` (desktop), `platform_api` (refresh-token reuse grace)
**Branch:** `fix/desktop-refresh-resilience`

## Summary

Support keeps seeing an **"Unauthenticated"** pill in the desktop status bar while
the footer still shows cached credits and profiles. Production logs confirm the
sequence (nginx + `camxora-api` journal, 1–8 Nov 2026):

- Desktop `POST /api/v3/auth/refresh` is slow or aborted: **17.6s, 47s, 56s,
  68s, 87s, 128s, 146s**, plus **10× 499** (client gave up) and **4× 502**.
- The next refresh attempt with the same refresh token returns **401 "This
  session has already been refreshed."** (`REFRESH_TOKEN_ROTATED`).
- Over 7 days: **726 OK vs 18 failed desktop refreshes** — every failure forced a
  re-login, and the user stayed in a logged-in shell showing cached data.

Root cause was client-side as much as server-side:

1. `PlatformClient._send()` called `clear_session()` on **any** refresh failure —
   including timeouts, connection drops and 5xx gateway errors.
2. A request whose access token was already being refreshed called
   `clear_session()` immediately instead of waiting for the renewal.
3. A second `401` after a **successful** refresh cleared the session even though
   a fresh token pair existed.
4. `run_bootstrap()` cleared saved tokens on any `get_me` error, including a
   network outage.
5. Server-side, a rotated token was only accepted for **15 seconds**, so a retry
   after a 17–146s refresh was treated as theft.
6. Two studio windows share one encrypted store; the second window could not see
   the pair rotated by the first and signed itself out.

## Product impact

- A dropped, slow or 5xx refresh no longer signs the user out. The app keeps the
  saved session and shows "Could not renew your session right now… your sign-in
  is still saved" instead of `Unauthenticated` on every poll.
- A second studio window (or a fast retry after a lost response) adopts the
  rotated token pair instead of clearing the account.
- Real sign-outs still happen: a server `401` for the refresh token (expired,
  revoked, rotated beyond the grace window) clears tokens exactly as before.
- The server-side grace window helps **existing installers** as soon as it is
  deployed; the client-side behaviour needs a new desktop release.

## Technical impact

- `camxora_python/shared/services/platform_client.py`
  - New `RefreshOutcome` enum (`REFRESHED` / `NOT_NEEDED` / `REJECTED` /
    `TRANSIENT`) and `_run_refresh()`, which classifies a refresh result.
  - `_send()` retries with a newer token when another thread rotated it, renews
    instead of clearing on the invalidated-token fast path, and never clears on
    `TRANSIENT` or on a second 401 after a successful refresh.
- `camxora_python/shared/services/session_service.py`
  - New `refresh_session() -> RefreshOutcome`; `ensure_fresh_session()` remains a
    bool wrapper for existing callers (keepalive timer, push runtime, tests).
  - Only a server 401 clears tokens. `_classify_refresh_failure()` returns
    `TRANSIENT` for network/5xx and keeps the session.
  - `_adopt_rotated_tokens()` re-reads the secure store and adopts a pair rotated
    by another app window.
  - `run_bootstrap()` no longer clears tokens on network/5xx/unexpected errors.
- `camxora_python/shared/services/secure_storage.py`
  - New non-destructive `reload()` (leaves the in-memory copy untouched when the
    file cannot be read right now).
- `platform_api/config.py`
  - New `refresh_reuse_grace_seconds` setting, default **180s**.
- `platform_api/services/auth_service.py`
  - `_revoked_within_grace()` takes the configured window; a retry after a
    dropped/slow refresh response is treated as a client retry, not credential
    theft.

## Files touched

| File | Change |
|---|---|
| `camxora_python/shared/services/platform_client.py` | Outcome enum, `_run_refresh`, resilient 401 handling |
| `camxora_python/shared/services/session_service.py` | `refresh_session`, failure classification, token adoption, bootstrap resilience |
| `camxora_python/shared/services/secure_storage.py` | Non-destructive `reload()` |
| `camxora_python/tests/test_platform_client_refresh_resilience.py` | New (8 tests) |
| `camxora_python/tests/test_session_refresh_outcome.py` | New (8 tests) |
| `platform_api/config.py` | `refresh_reuse_grace_seconds` |
| `platform_api/services/auth_service.py` | Configurable reuse grace |
| `platform_api/tests/test_refresh_reuse.py` | Grace pinned in the stale case + retry-after-60s test |

## Migration/deploy

No schema change and no migration. Deploy `platform_api` for the grace window;
ship the next desktop installer for the client behaviour. Existing v1.6.2
installs still get the server-side grace improvement immediately.

## Tests

```bash
cd camxora_python
python -m pytest tests/test_session_refresh.py tests/test_session_refresh_outcome.py \
  tests/test_platform_client_refresh_resilience.py tests/test_login_api.py \
  tests/test_session.py tests/test_platform_api.py -q
# 28 passed (targeted run; broader platform/session subset 71 passed)

python -m ruff check shared/services/platform_client.py shared/services/session_service.py \
  shared/services/secure_storage.py tests/test_platform_client_refresh_resilience.py \
  tests/test_session_refresh_outcome.py
# All checks passed

cd ..
python -m pytest platform_api/tests/test_refresh_reuse.py platform_api/tests/test_auth_router.py -q
# 31 passed
```

## Follow-ups

- `POST /api/v3/auth/refresh` latency (DB pool `min_size=4, max_size=8` per
  worker, `pool is closing` events under load) — the client now survives it, but
  the endpoint should not take 17–146s.
- `music.camxora.com/create` loops `POST /auth/refresh` every ~3s while signed
  out (3 812 browser 401s/week, all "Refresh token is required") — separate web
  fix.
- Desktop log sync is dead in production: `client_log_batches` has one row total
  (newest 2026-08-08), so support still has no in-app evidence trail.
