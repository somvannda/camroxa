# Desktop UI: one credits number, no Plan quota (2026-08-22)

## What shipped
Desktop Studio chrome now shows **one credits wallet number**. Song / draft / image / video / merge **plan meters** are off the main user-facing dashboard and membership cards. Generate still works. Charge flag stays **Off**. Production not touched. Leftover mint not applied. Admin `/plans` and admin usage/finance/user work from earlier passes not reverted.

## Desktop
- Dashboard remaining card: credits balance + spent this month only. Removed draft/Suno/image/export/merge meters and today (account) video/merge leftover counts.
- Daily channel limits card unmounted from the dashboard (widget file still in tree, unused).
- Profile membership: kept plan name, credits balance, expiry, profile allowance bar, add-on channel fields. Removed Monthly songs bar and Song quota field.
- Music Generate: no "Generate (Plan quota)" / "Generate drafts (Plan)". Subscription-covered runs say Generate / Generate drafts. Wallet cost label unchanged when not covered. Preflight still gates generate.
- Sidebar/status bar already showed `credit_balance` (including 0).
- Image $0-wallet warning no longer tells the user leftover image counts are the plan.

## Not done
- Charge flag flip / `subscription_covers_*` retirement
- Conversion apply / leftover mint
- v3 wallet API wiring (still license/me wallet number)
- User portal / website / Web Music cards
- Production
