# Sandbox billing cutover (API v3 wallet)

## Summary

Sandbox end-of-month-style cutover for credits-only wallet:

- Admin catalog grants locked (desktop subscription plans get `monthly_credits` from song limits; hidden **Monthly · 2-channel** `$79` stays `is_public=false` with **3000** monthly credits).
- Leftover desktop quota conversion applied (idempotent; already minting recorded).
- Web CutLuy ledger conversion dry-run shows already applied.
- `credits_only_v3_charge=true` on sandbox.
- Legacy `plan_usage.songs_used` zeroed for open periods.
- Renewals continue to use Admin plan `monthly_credits` via `ensure_period_grant` (same `plan_id`, no remap of $79 → Starter).

Production cutover is **not** run (sandbox only).

## Force-upgrade note

Desktop client is version **1.3.2** on `/api/v3`. Publish a **mandatory** software-update in Admin when the installer is built so field clients leave `/api/v1`.
