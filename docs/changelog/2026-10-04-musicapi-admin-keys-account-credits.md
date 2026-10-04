# musicapi: admin API Keys grouped by owner with account-level credits

## Summary

The admin **API Keys** page listed every key flat and showed the raw
`api_keys.credits` column per key. Because purchased credits physically land on
one key (the target of the top-up, or an auto-created wallet key) while spending
is pooled across **all** of a user's active keys, the page read as if every newly
created key were an empty wallet — only the key that received the top-up showed a
balance.

Credits are account-level: `charge()` falls back to `chargeUserKey()` to spend
from any funded key the user owns, `/me/billing` and `/admin/users` both sum
across keys, and deleting a funded key moves its balance to another key. The
admin view now reflects that:

- `GET /admin/keys` also returns `user_id`, `account_credits` (the sum across the
  owner's keys) and `key_count`.
- The page groups keys by owner. Each owner header shows the key count and the
  **Account total**; each key row shows its own per-key balance under a
  **Key Balance** column.

## Product impact

- A user with one funded key and several 0-balance keys now shows the pooled
  total once, instead of looking like four separate wallets.
- The subtitle states credits are pooled per account so any key spends the
  owner's total.
- No spend behavior change: keys already drew on the pooled balance.

## Technical impact

- `musicapi/src/server.ts` — `/admin/keys` query adds `k.user_id`,
  `account_credits` (subquery sum) and `key_count`; ordered by `u.email,
  k.created_at DESC` for stable grouping.
- `musicapi/web-admin/app/admin/keys/page.tsx` — groups rows by `user_id`,
  renders per-owner header rows, adds an **Account total** figure and a
  **Key Balance** column, and keeps the existing search (now also matches key
  name).

## Files touched

- `musicapi/src/server.ts`
- `musicapi/web-admin/app/admin/keys/page.tsx`
- `docs/changelog/2026-10-04-musicapi-admin-keys-account-credits.md`

## Tests

- `npm run typecheck` in `musicapi` → clean.
- `npm run typecheck` in `musicapi/web-admin` → clean.
- `npm run lint` in `musicapi/web-admin` → only the repo's pre-existing
  `react-hooks/set-state-in-effect` errors on every page (the original keys page
  had the same); no new lint findings from this change.
