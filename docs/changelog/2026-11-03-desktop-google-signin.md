# Desktop: Google sign-in

**Date:** 2026-11-03
**Surfaces:** `camxora_python` (desktop studio), `music_web`, `platform_api`

## Summary

Adds **Continue with Google** to the desktop sign-in card, reusing the exact Google OAuth client
and redirect URI that music.camxora.com already uses. Nothing new needs to be registered in Google
Cloud Console: Google still redirects to the registered https callback, and that page hands the
browser over to the app.

1. The desktop binds a one-shot listener on `http://127.0.0.1:41580/google/callback`.
2. It calls `GET /api/v3/auth/google/url?desktop_port=41580`. The API keeps the registered
   `https://music.camxora.com/auth/callback` redirect and signs the port into the OAuth `state`.
3. The browser performs consent and lands on `https://music.camxora.com/auth/callback?code=…&state=…`.
   That page sees `desktop_port` in the state and **forwards the browser** to the loopback listener
   instead of signing the browser in ("Returning to the CAMXORA studio…").
4. The desktop posts `{code, state}` to `POST /api/v3/auth/google/callback`, which verifies the
   signed state (with the port) and exchanges the code using the server-held client secret. The
   desktop stores the token pair exactly like a password login and runs the normal bootstrap.

Tokens never travel through the browser; the browser only carries an authorization code that is
useless without the client secret and the signed state.

## Product impact

- Desktop users can sign in (or create an account) with Google instead of typing a password.
- No Google Cloud Console change and no extra production secret: the desktop piggybacks on the
  music.camxora.com OAuth client that is already live.
- The desktop paid-entitlement gate still applies: a free account signing in with Google gets the
  same "desktop studio requires a paid plan" message as the password path (enforced server-side
  with `X-Camxora-Client: desktop`).
- Cancelled consent, a busy port, a closed browser and a timeout each produce a specific message
  instead of a generic failure.

## Technical impact

`platform_api`

- `services/email_link_tokens.py`: `sign_oauth_state(redirect_uri, desktop_port=None)` signs the
  loopback port into the state; `oauth_state_desktop_port()` reads it back (1–65535, else `None`).
- `routers/auth.py`: `/google/url` accepts `desktop_port` (1–65535) and keeps the allowlisted https
  redirect; `/google/callback` now also enforces `assert_paid_desktop_access()` for desktop clients.
- The redirect allowlist is unchanged — loopback URIs are **not** accepted from Google.

`music_web`

- `lib/oauth-state.ts`: `desktopHandoffPort()` (base64url-decodes the signed state payload for
  routing only) and `desktopHandoffUrl()` (always `127.0.0.1`, port validated).
- `app/auth/callback/page.tsx`: when the state carries `desktop_port`, forward the browser to the
  loopback listener — including `?error=` so a cancelled consent reaches the app immediately.

`camxora_python`

- `shared/services/google_desktop_oauth.py`: `GoogleLoopbackServer` (fixed port, exclusive bind on
  Windows so two windows cannot share it, `CAMXORA_OAUTH_LOOPBACK_PORT` override, 300 s timeout,
  success/failure HTML, first-response-wins).
- `shared/services/platform_api.py`: `google_auth_url(desktop_port)` / `google_callback(code, state)`.
- `shared/services/session_service.py`: `google_authorization_url(desktop_port=…)` /
  `complete_google_login(code, state)`.
- `shared/workers/bootstrap_worker.py`: `GoogleAuthWorker` (browser + loopback off the UI thread)
  and a shared `_paid_plan_result()` helper for the desktop-plan gate.
- `features/account/views/auth_view.py` + `auth_styles.py`: "Continue with Google" button
  (`auth_google_button`), busy-state handling and the `google_signin_requested` signal.
- `app/root_window.py`: wires the button through the mandatory-update check into the worker.

## Deploy / configuration

- No Google Cloud Console change. `GOOGLE_CLIENT_ID` / `GOOGLE_CLIENT_SECRET` must already be set on
  platform_api (they are, for music.camxora.com); `GET /auth/google/url` returns 503 otherwise.
- Deploy order: `platform_api` → `music_web` (the forwarding page) → desktop build. An older
  website would simply finish the sign-in in the browser and the app would time out with a clear
  message.
- No schema change.

## Tests

- `platform_api/tests/test_google_desktop_handoff.py` — 9 tests: state round-trips the port,
  browser state stays portless, out-of-range ports ignored, `/google/url` keeps the registered
  https redirect for `desktop_port`, browser flow unchanged, invalid port → 422, loopback redirect
  still → 422, unconfigured Google → 503.
- `music_web/src/lib/oauth-state.test.ts` — 6 tests: port decoding (valid/invalid/malformed),
  hand-off URL construction and cancellation relay, always 127.0.0.1.
- `camxora_python/tests/test_google_desktop_oauth.py` — 9 tests: code+state capture, cancelled
  consent, unknown path, timeout, busy port, env port override, worker success / missing browser /
  API failure.
- `camxora_python/tests/test_auth_login_ui.py` — asserts the Google button exists and emits
  `google_signin_requested`.
- `python -m pytest platform_api/tests -k "auth or google"` — 113 passed.
- `camxora_python/tests -k "auth or google or login or session or bootstrap"` — 71 passed.
- `npm test` (music_web) — 63 passed.

## Follow-ups

- Pre-existing, unrelated: `camxora_python/tests/test_application.py::test_router_navigates_all_routes`
  fails on `origin/main` because `app/router.py` imports a `features.logs` module that is not in
  this tree.
- Consider PKCE (`code_challenge`) on the browser leg as defence in depth.
- The hand-off only works when the browser and the desktop are on the same machine (loopback by
  design); a future remote-desktop case would need a device-code flow.
