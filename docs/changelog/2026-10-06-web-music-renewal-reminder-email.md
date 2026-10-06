# Web-music renewal reminder emails — 2026-10-06

**Surfaces:** `platform_api/` (email service + subscription maintenance).

## Why

CutLuy is one-time, so a web-music period ends unless the user renews. With the
renewal checkout (PR #355) and UI (PR #357) live, users need a nudge before the
period ends. `web_subscriptions.renewal_reminder_sent_at` (migration 135) was
reserved for exactly this.

## What changed

- `platform_api/config.py` — `music_web_base_url` (default
  `https://music.camxora.com`) for the renewal link.
- `platform_api/services/email_service.py` — extracted a shared `_send(msg, to)`
  (reused by the verification email) and added `_build_renewal_reminder_email` +
  `send_renewal_reminder_email`.
- `platform_api/services/v2/subscription_service.py` —
  `list_renewal_reminders_due(within_days=RENEWAL_WINDOW_DAYS)` (active, not
  cancelled, unreminded, within the window) and `mark_renewal_reminder_sent(id)`;
  `_fulfill_renewal` now resets `renewal_reminder_sent_at` for the next period.
- `platform_api/services/renewal_reminder_service.py` (new) —
  `run_renewal_reminders(pool)`: sends reminders off-thread, marks each sent; a
  failed send is retried on the next sweep.
- `platform_api/main.py` — a 6-hourly `web-music-renewal-reminders` task.

## Behaviour

- Reminders go out inside the 7-day renewal window (matching the checkout window)
  to active, non-cancelling, paid subscribers; one per period.
- Sending is best-effort: an SMTP failure logs and does not mark the row sent, so
  it retries later; the loop never crashes startup.

## Verification

- `platform_api/tests/test_web_music_renewal_reminder.py` (price formatting, email
  subject/body/link, today/soon wording).
- Made the renewal-offer `days_left` assertions boundary-tolerant (`timedelta.days`
  truncation) in `test_web_music_subscription_renewal.py`.
- Focused suites: 18 passed.

## Follow-ups

- **Confirm production SMTP** (`PLATFORM_SMTP_*` / `configure_smtp_production.py`);
  the loop no-ops safely if unset.
- Extend `renewal_alert` to web subs; credit-period anchoring.
