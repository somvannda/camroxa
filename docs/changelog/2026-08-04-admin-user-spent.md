# Admin User Spent page

## Summary

New admin **User Spent** roster at `/user-spent` lists users by estimated USD COGS, with expandable provider × operation breakdowns and alerts for plan-meter overage and margin risk.

## Surfaces

- **platform_api:** `GET /api/v1/admin/user-spend` — per-user ledger rollup, est. COGS (pricing / model costs), plan meters, soft-overage + margin-risk flags.
- **admin_portal:** Sidebar **User Spent**, dense expandable table, StatCards, filters (date / plan / alert / provider / operation), deep-links to Usage ledger and user detail.

## Notes

- Est. COGS is **estimated** from admin model costs / pricing `external_cost_cents`, not provider invoices.
- Plan revenue used for margin risk is **prorated** by selected date range ÷ `billing_cycle_days`.
- Free users only flag margin risk when est. COGS exceeds $1 to reduce noise.
