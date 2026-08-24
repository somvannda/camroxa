# Credits-only Admin Plans + flagged Generate charge (2026-08-22)

## What shipped
Admin **Plans** can set period grants, per-op amounts, and public/active on the same plan rows as v1. A **Debit Generate via v3** flag (default off) makes desktop/web generate debit the shared wallet instead of quota-first.

## Admin
New **Credits-only billing** card on Plans:
- `monthly_credits` / `daily_credits`
- per-op amounts (`lyric` / `title` / `album` / `music` / `style` / `image` / `video` / `merge`)
- empty = Credits page fallback; `0` = included
- `is_public` / `is_active` (keep hidden $79 active + not public)
- system setting `credits_only_v3_charge` (overrides `PLATFORM_CREDITS_ONLY_V3_CHARGE`)

Saves go to `PATCH /api/v3/admin/plans/{id}`. Create uses v1 POST (leftover quota columns sent as zeros, not shown) then the same v3 PATCH.

## Admin /plans catalog (5b)
The live Plans page is now one catalog:
- **Kept:** Credits-only billing card (list, edit grants / per-op / active / public, create, Generate flag display Off), promotional offers.
- **Unmounted from the page (files still in repo):** ChannelPricingSection, MusicWebFreeCreditsSection, WebMusicPlansSection, SubscriptionPlansSection, PlanLimitsFields, channel price calculators.
- `web_music_free_daily_credits` setting is **not** deleted (doc 8b).

## Generate
When the flag is on, `check_and_deduct`, `deduct_for_operation`, and image reserve/hold charge via v3 and skip song/draft meters. Flag off = today’s quota-first path.

## Not done
- Conversion apply
- Seeding Starter / Creator / Studio as public
- Turning the flag on in sandbox or production
- Lifetime leftover conversion
