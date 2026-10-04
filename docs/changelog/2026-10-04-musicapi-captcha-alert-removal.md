# musicapi: remove the false "captcha locked" alert

## Summary

PR #225 (`fix/musicapi-captcha-health`) already made a captcha challenge
non-fatal: `/admin/accounts` and `/admin/stats` now expose `captcha_solver`, a
captcha-required account counts as `healthy` when a 2Captcha key is configured,
and the badge reads "Captcha auto-solve" (sky) instead of "Captcha required"
(amber).

One surface was missed: the alert evaluator still raised a `captcha_locked`
warning whenever `POST /api/c/check` returned `required=true`, and the Settings
→ Alerts tab still exposed the "Alert when Suno is captcha-locked" toggle plus a
"Captcha locked" stat. That condition is never actionable — the worker solves
the Turnstile automatically at generation time — so it only produced noise
(Turnstile solves are routine, not a fault) and could page the ops Telegram
channel.

This change removes the captcha alert entirely. Low-credits and failure-rate
alerts are unchanged.

## Product impact

- No more `captcha_locked` warnings in `GET /admin/alerts`, and no Telegram
  `[ALERT] ... captcha_locked` / `[RESOLVED] ... captcha_locked cleared`
  messages.
- Settings → Alerts no longer shows the "Alert when Suno is captcha-locked"
  toggle, and the Live alerts panel no longer shows a "Captcha locked" stat.
- The solver-aware badge and `healthy` behaviour from PR #225 are untouched: a
  captcha-required account is still amber "Captcha required" only when **no**
  solver is configured.

## Technical impact

- `musicapi/src/server.ts`
  - Dropped the `captcha_locked` field from `AlertSettings`, `DEFAULT_ALERTS`,
    `coerceAlerts()`, `mergeAlerts()`, `AlertType` and the `/admin/alerts`
    summary; removed the corresponding block in `evaluateAlerts()`; removed the
    now-unused `captchaRequired` import.
- `musicapi/web-admin/app/admin/settings/page.tsx`
  - Removed the `captcha_locked` fields from the local `AlertSettings` /
    `AlertReport` types, the alerts toggle, and the "Captcha locked" stat; the
    live-alerts summary grid drops to 3 columns.
- `musicapi/REQUIREMENTS.md` §4.10 updated to list only the remaining alerts.

No route, schema, or environment change; a stored `captcha_locked` value in
`app_settings.alerts` is simply ignored.

## Files touched

- `musicapi/src/server.ts`
- `musicapi/web-admin/app/admin/settings/page.tsx`
- `musicapi/REQUIREMENTS.md`
- `docs/changelog/2026-10-04-musicapi-captcha-alert-removal.md`

## Tests

- `npm run typecheck` in `musicapi` → clean.
- `npm run typecheck` in `musicapi/web-admin` → clean.
- `grep captcha_locked musicapi` → no code references (only a historical plan
  doc under `docs/`).
