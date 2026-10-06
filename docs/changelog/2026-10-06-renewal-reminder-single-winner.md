# Renewal reminders: single-winner sweep — 2026-10-06

**Surfaces:** `platform_api/services/renewal_reminder_service.py`.

## Why

The 6-hourly renewal reminder loop runs in every uvicorn worker. Production logs
showed the same reminder sent twice (two workers) to the same user:
`Renewal reminder email sent to teangchunpanhavorn@gmail.com` ×2. The sweep had no
single-winner guard, so workers raced between `list_renewal_reminders_due()` and
`mark_renewal_reminder_sent()`.

## What changed

- `run_renewal_reminders()` now takes a Postgres advisory lock
  (`pg_try_advisory_lock`, id `774319003`, distinct from grant maintenance's) and
  returns early when another worker holds it; only the winner runs the sweep.
  The previous body moved to `_run_renewal_reminders()`.

## Verification

- `py_compile` + import OK; reminder email tests: 3 passed.
- (Pre-fix) production log confirmed a duplicate send; expected single send after
  this change.
