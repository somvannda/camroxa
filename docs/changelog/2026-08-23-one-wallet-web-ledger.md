# 2026-08-23 — One wallet: CutLuy leftover + generate on credit_wallets

Sandbox only until you ask for production. Complete set for item 17.

CutLuy paid-plan fulfill and monthly reset mint the period grant on `credit_wallets`, then zero leftover monthly on `web_subscriptions` so a later leftover job cannot double-count. Top-up fulfill mints a non-expiring `pack` lot (idempotent by `v3_pack:{topup_id}`) and subtracts the same amount from the v2 top-up pot.

One-time leftover: `max(0, unused monthly + topup)` → `quota_conversion` lot (`v3_web_remaining`). Does not use `billing_conversion_runs` (desktop leftover already occupies that unique-per-user row). Expired / $0 rows are skipped.

Generate no longer falls back to v2. Empty v3 wallet is 402. Web header / Create / profile use `/api/v3/me/credits` only; v2 balance is a hard fallback if that request fails.

Production later: deploy this code, then run `run_web_ledger_conversion_production.py --i-mean-production` (dry-run) and `--apply` once. Do not run that script until asked.
