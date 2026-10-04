# musicapi: honest captcha alerts (replace the removed false one)

## Summary

The previous commit removed the `captcha_locked` alert because it fired
whenever Suno presented a Turnstile — which the worker solves automatically via
2Captcha — making it pure noise. That left a blind spot: nothing alerted when a
captcha *genuinely* blocks generation.

This adds two captcha alerts that only fire when the condition is actionable:

1. **`captcha_no_solver`** — one or more accounts require a captcha but no
   2Captcha key is configured. Generation on those accounts will fail.
2. **`captcha_balance`** — a 2Captcha key is configured but its balance is at or
   below `captcha_balance_threshold` USD (default **$1**, `0` disables the
   check). This is the proactive signal for the "solver runs dry" case.

Both flow through the existing `GET /admin/alerts` evaluator, dedupe and ops
Telegram delivery, exactly like low-credits and failure-rate alerts.

## Product impact

- Settings → Alerts gains a **"2Captcha balance threshold ($)"** field.
- Settings → Status shows **"Captcha accounts"** and **"2Captcha balance"**
  stats, and the captcha alerts appear in the live-alerts list/Telegram only
  when they are real.
- A routine captcha challenge with a funded key stays silent (PR #225's
  solver-aware "Captcha auto-solve" badge already covers the UI).

## Technical impact

- `musicapi/src/server.ts`
  - `AlertSettings` / `DEFAULT_ALERTS` / `coerceAlerts()` / `mergeAlerts()` gain
    `captcha_balance_threshold` (USD, default 1, `0` disables).
  - `AlertType` gains `captcha_no_solver` and `captcha_balance`; the
    `/admin/alerts` summary gains `captcha_required` (count) and
    `captcha_balance` (USD or null).
  - New `fetchTwoCaptchaBalance()` (8 s timeout, never throws — a failed probe
    yields `null` and produces no alert).
  - `evaluateAlerts()` adds the two captcha conditions after the low-credits
    check.
- `musicapi/web-admin/app/admin/settings/page.tsx`
  - `AlertSettings` / `AlertReport` types updated; new threshold input and two
    new Status stats.
- `musicapi/REQUIREMENTS.md` §4.10 updated.

No route or schema change. `captcha_balance_threshold` defaults to 1 for
existing installs.

## Files touched

- `musicapi/src/server.ts`
- `musicapi/web-admin/app/admin/settings/page.tsx`
- `musicapi/REQUIREMENTS.md`
- `docs/changelog/2026-10-04-musicapi-captcha-health-alerts.md`

## Tests

- `npm run typecheck` (musicapi) → clean.
- `npm run build` (musicapi) → clean.
- `npm run typecheck` (musicapi/web-admin) → clean.
- 2Captcha `getbalance` response shape verified: `{"status":1,"request":"2.86312"}`
  → parsed as USD `2.86`.
