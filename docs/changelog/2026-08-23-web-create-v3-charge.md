# 2026-08-23 — Web Create uses the credits-only charge model

Sandbox only. Production not touched.

Matches `docs/credits-only-plan-unification.md` §4.1 / §4.2 / §5.4 / §6. Item 17 (one wallet) stays later.

## Charge model

When `credits_only_v3_charge` is **On**:

- Web Create music generate quotes `plan.music_credits` and debits **10**. Desktop Pro / $79 no longer skip the charge.
- Lyrics assist uses the **`lyric`** op (not `web_music_lyrics` pricing). Style assist uses **`style`**.
- Free daily credits come from the Free plan row via a v3 `daily_grant` lot (expires at next billing midnight).
- Failed Suno / text assist refunds the same path that charged.

## Two ledgers remain

CutLuy / `web_subscriptions` still debit the v2 ledger for the **same quoted amount**. Checkout is unchanged. Do not treat this as the later one-wallet project.

## Create UI

Paid users with fewer than 10 credits see the upgrade gate. `is_pro` no longer means unlimited generates.
