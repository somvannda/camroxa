# Subscription maintenance: report expiries — 2026-10-06

**Surfaces:** `platform_api/services/v2/subscription_service.py`.

## Why

After the stop-free-auto-renewal change, `reset_quota_if_needed()` no longer
renews — it expires ended periods and returns `False`. `process_due_subscriptions()`
only counted `True` results, so every sweep logged `handled=0` even when it had
just expired subscriptions, making the work invisible in logs/metrics.

## What changed

`process_due_subscriptions()` now counts ended periods as `expired` (they all
expire under the current rule) and yearly mid-term refreshes as `refreshed`, logs
`"Web music subscription maintenance: expired=N refreshed=M"`, and returns the
sum (preserving the previous "rows handled" contract).

## Verification

- `py_compile` OK.
- Focused suites (`test_web_music_subscription_credit_reset`,
  `test_web_music_subscription_renewal`, `test_web_music_renewal_reminder`):
  18 passed.
