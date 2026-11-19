# 1. Login, Auth, Onboarding and Update Gate

> **Feature prefix:** `LG-`
> **Route:** `/auth` (login/register), `/onboarding` (gates), startup splash
> **Phase:** P1
> **Sources of truth:**
> - `camxora_python/features/account/views/auth_view.py`
> - `camxora_python/features/account/views/startup_view.py`
> - `camxora_python/features/account/views/upgrade_plans_dialog.py`
> - `camxora_python/features/onboarding/views/onboarding_views.py`
> - `camxora_python/app/root_window.py`
> - `camxora_python/shared/services/session_service.py`
> - `camxora_python/shared/services/google_desktop_oauth.py`
> - `camxora_python/shared/services/software_update_service.py`
> - `camxora_python/shared/services/software_update_installer.py`
> - `camxora_python/shared/widgets/software_update_gate.py`

---

## 1. Purpose

Get a valid, entitled user into the app safely, and keep them out with a clear explanation
when they are not entitled or not configured. This page also owns the startup/update gates
that run before the shell.

---

## 2. Entry and exit points

| From | Condition | Goes to |
|---|---|---|
| App launch | No valid session | Startup → Login |
| App launch | Valid stored session + entitled | Startup → Dashboard |
| App launch | Valid session, email unconfirmed | Onboarding welcome |
| App launch | Valid session, no channel profiles | Onboarding wizard |
| Login success | Entitled | Dashboard (or the intended route) |
| Login success | Not entitled | Upgrade plans dialog; stays on login |
| Login success | Unconfirmed email | Onboarding welcome |
| Logout | Any page | Login, caches cleared |
| Session refresh failure | Any page | Login with a session-expired message |

---

## 3. Startup and update gate

| ID | Feature | Acceptance | Pri |
|---|---|---|---|
| LG-01 | Startup splash | Window shows brand, a progress line and a status label; it never shows an unstyled white flash | P0 |
| LG-02 | Bootstrap progress | Steps report a label, detail and percentage; the last step is "Ready" before the shell appears | P0 |
| LG-03 | Bootstrap retry | A failed step shows the error and a Retry action; retry re-runs bootstrap without restarting the app | P0 |
| LG-04 | Mandatory update check | On start, the app checks the release channel before auth; a mandatory release blocks login with version and reason | P0 |
| LG-05 | Optional update offer | A newer non-mandatory release shows a quiet "Update available" action; the user can continue | P1 |
| LG-06 | Update download/install | Progress is visible (message + percent), cancel is not offered for mandatory, and the app relaunches after install | P0 |
| LG-07 | Update failure | A failed install restores the prior version, shows the persisted error and a manual download link | P0 |
| LG-08 | Stale/withdrawn release | If the offered version is no longer newer or was withdrawn, the gate clears and login continues | P1 |
| LG-09 | Offline update check | If the release endpoint is unreachable, the app continues unless a mandatory update is already persisted and active | P0 |
| LG-10 | Version and environment | The login footer shows app version and environment (sandbox/production); a click opens build info | P1 |

---

## 4. Login

| ID | Feature | Acceptance | Pri |
|---|---|---|---|
| LG-11 | Email field | Accepts an email, trims whitespace, validates on blur, Enter moves to password | P0 |
| LG-12 | Password field | Masked with a show/hide control, Enter submits, no copy/paste blocking | P0 |
| LG-13 | Remember me | Checked stores an OS-encrypted refresh token; unchecked keeps the session in memory only | P0 |
| LG-14 | Submit | Button shows a loading state, disables duplicate submits, and reports a specific error | P0 |
| LG-15 | Error handling | Wrong credentials, unverified email, network failure and server error each have distinct copy | P0 |
| LG-16 | Recent accounts | Saved accounts list shows avatar/initials, name/email, last used; selecting one prefills the email | P0 |
| LG-17 | Remove saved account | A row action removes the saved account after confirmation; no token is left behind | P1 |
| LG-18 | Forgot password | Opens the account portal in the system browser; the app stays open | P0 |
| LG-19 | Create account link | Visible only when registration is enabled; switches to the register form | P0 |
| LG-20 | Save diagnostics | Saves a redacted diagnostics bundle without signing in; success shows the file path | P1 |
| LG-21 | Keyboard | Tab order is email → password → remember → sign in → Google; Escape clears the error | P0 |
| LG-22 | Autofill | Email/password use correct `autocomplete` attributes and are not treated as search fields | P1 |

---

## 5. Register

| ID | Feature | Acceptance | Pri |
|---|---|---|---|
| LG-23 | Register form | Email, password, display name; inline validation; Enter submits | P0 |
| LG-24 | Register success | Creates the account, signs in, and routes to the correct gate (onboarding or dashboard) | P0 |
| LG-25 | Register failure | Duplicate email, weak password and network failure have distinct messages | P0 |
| LG-26 | Back to sign in | Returns to login, preserving the entered email | P1 |
| LG-27 | Registration disabled | If the flag is off, the create-account link and form are absent, not disabled | P1 |

---

## 6. Google sign-in

| ID | Feature | Acceptance | Pri |
|---|---|---|---|
| LG-28 | Google button | Starts the system-browser flow; shows "Waiting for browser…" with a cancel action | P0 |
| LG-29 | Loopback callback | Main-process listener accepts one callback, validates state, exchanges the code, closes | P0 |
| LG-30 | Cancel/timeout | Cancel closes the listener; a 3-minute timeout returns to login with a clear message | P0 |
| LG-31 | Account mismatch | If the Google account cannot access the desktop plan, the paid gate applies | P0 |
| LG-32 | Fallback protocol | If the loopback is blocked, `camxora://auth/callback` completes the same flow | P1 |

---

## 7. Entitlement, confirmation and onboarding

| ID | Feature | Acceptance | Pri |
|---|---|---|---|
| LG-33 | Paid-access gate | A user without live desktop entitlement sees a dedicated message, not a generic error | P0 |
| LG-34 | Upgrade plans dialog | Shows current plan, available packs/plans, credits/term, and a "Open account portal" action | P0 |
| LG-35 | Gate re-check | After returning from the portal, Refresh re-runs entitlement without a full restart | P0 |
| LG-36 | Email-confirmation gate | Unconfirmed users see the confirmation panel with "Open account portal" and "Back to sign in" | P0 |
| LG-37 | Onboarding gate | Users without profiles see "Complete setup in your browser", "I completed setup — refresh", "Open studio anyway" | P0 |
| LG-38 | Onboarding refresh | Refresh re-runs bootstrap and routes to the shell when profiles exist | P0 |
| LG-39 | Onboarding skip | "Open studio anyway" enters the shell; pages that need profiles explain what is missing | P1 |
| LG-40 | Session restore | A valid stored refresh token restores the session without a password prompt | P0 |
| LG-41 | Session expiry | A failed refresh returns to login with "Session expired. Please sign in again." and keeps the intended route | P0 |
| LG-42 | Logout | Clears tokens, query cache, per-user caches; returns to login; never deletes user files | P0 |
| LG-43 | Switch account | Selecting a different saved account tears down the current session and starts a new one | P1 |

---

## 8. Layout and states

```
┌──────────────────────────────────────────────────────────────┐
│  (drag region)                                               │
│                                                              │
│                    CAMXORA                                   │
│                    FACELESS DESKTOP STUDIO                   │
│                                                              │
│                 ┌──────────────────────────┐                 │
│                 │ Welcome back             │                 │
│                 │ Sign in to your studio   │                 │
│                 │                          │                 │
│                 │ Email                    │                 │
│                 │ [______________________] │                 │
│                 │ Password                 │                 │
│                 │ [______________________] │                 │
│                 │ [x] Remember   Forgot?   │                 │
│                 │                          │                 │
│                 │ [ Sign in              ] │                 │
│                 │ [ Continue with Google ] │                 │
│                 │ Save diagnostics         │                 │
│                 │                          │                 │
│                 │ Recent accounts          │                 │
│                 │ • user@example.com       │                 │
│                 └──────────────────────────┘                 │
│                                                              │
│  2.0.0 · sandbox                                             │
└──────────────────────────────────────────────────────────────┘
```

| State | Behaviour |
|---|---|
| Idle | Form enabled; no error |
| Submitting | Button spinner; fields read-only; duplicate submit blocked |
| Error | Inline banner above the form; fields remain editable |
| Google waiting | Button becomes "Waiting for browser…" with Cancel |
| Gate | Login form replaced by entitlement/confirmation/onboarding panel |
| Update | Blocking overlay with progress if mandatory; quiet banner if optional |
| Offline | Banner "Cannot reach Camxora. Check your connection."; Retry |

---

## 9. Non-functional

| ID | Requirement |
|---|---|
| LG-N1 | No password or token is ever logged or written to disk in plaintext |
| LG-N2 | Login response is not persisted in the query cache |
| LG-N3 | The splash and login are usable at 1280×800 |
| LG-N4 | The window can be moved by dragging the top region; buttons are not draggable |
| LG-N5 | A second launch focuses the existing window and exits |
| LG-N6 | The login screen renders without the backend, with a clear offline state |

---

## 10. Tests

| ID | Scenario | Assert |
|---|---|---|
| LG-T1 | Successful login | Dashboard loads; session summary is present |
| LG-T2 | Wrong password | Inline error; no navigation |
| LG-T3 | Unconfirmed email | Confirmation gate, not dashboard |
| LG-T4 | No entitlement | Plans dialog + gate copy |
| LG-T5 | Remember me | Restart restores session without login |
| LG-T6 | Logout | Login screen; no cached user data |
| LG-T7 | Google cancel | Returns to login, no stuck spinner |
| LG-T8 | Update mandatory | Login blocked until install or explicit quit |
| LG-T9 | Offline start | Offline banner; retry works |
| LG-T10 | Recent account select | Email prefilled; remove works |

---

## 11. Definition of Done

- [ ] LG-01 … LG-43 implemented; `P0` items verified against sandbox `platform_api`.
- [ ] Loading, error, gate, offline and update states verified.
- [ ] No token/password appears in logs, diagnostics or crash reports.
- [ ] Keyboard-only flow completed.
- [ ] Visual baseline approved at 1440×900.
- [ ] LG-T1 … LG-T10 pass.
- [ ] Traceability updated in [`../07-TRACEABILITY.md`](../07-TRACEABILITY.md).
