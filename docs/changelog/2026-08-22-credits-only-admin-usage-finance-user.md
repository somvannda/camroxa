# Admin credits-only pages (user, usage, finance, user-spent) (2026-08-22)

## What shipped
Admin screens that still showed song/draft/image/video/merge **quota meters** now follow credits-only. Generate flag stays **Off**. Production not touched. Leftover mint not applied. `web_music_free_daily_credits` not deleted. `/plans` 5b catalog not reverted.

## Admin
- `/users/:id`: retired quota table + quota top-up. Shows wallet + period grant remaining (GET `/api/v3/users/:id/credits`) and grant lots. Wallet adjust kept. Other user admin unchanged.
- `/usage`: stats recast. Ledger kept. Historical `plan_allowance` stays labeled. New rows = wallet or `plan_included` (amount 0). Not rewritten as fake wallet debits.
- `/finance`: "plan included" cards recast to grant issued. Cash, wallet, COGS, absorb kept.
- `/user-spent`: dropped 5 meter chips and `over_allowance`. Kept COGS vs plan cash.
- Copy-only: `/licenses` (active plans including unpublished; not "quotas scale"), `/pipeline` (charges credits; waive_billing stays), Settings fail-absorb (refunds credits).
- `/credits` left as-is (pack label already "Credits included"). `/users` list wallet column unchanged.

## Not done
- Charge flag flip
- Conversion apply / leftover mint
- Production catalog
- Deleting `web_music_free_daily_credits`
