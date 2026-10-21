# platform_api: Free-plan web music is V6-Mini-only until a pack purchase

## Summary

`music.camxora.com` runs on platform_api/music_web. The Free plan row already
grants **50 credits per calendar month** into the shared wallet (V3
`period_grant_service`), but those credits were spendable on any model. This
change makes the Free grant V6-Mini-only until the user buys a credit pack in
the same calendar month.

- Free plan, V6-Mini → allowed (wallet debit).
- Free plan, V6-Pro / V6-Wild, no pack this month → rejected with
  "V6-Pro requires purchased credits. Buy a credit pack…".
- Free plan, V6-Pro / V6-Wild after a completed top-up this month, or while the
  wallet exceeds the monthly grant → allowed.
- Paid plans → unrestricted.
- Telegram is unchanged: every successful `consume_credits` / wallet debit still
  posts the SPEND event and appears in the 10 PM burn report.

## Product impact

- A new free account can make 5 V6-Mini generations (10 songs) per month and
  cannot use V6-Pro / V6-Wild until it buys a pack.
- Buying any pack unlocks the remaining monthly grant for premium models for the
  rest of that calendar month.
- No change to pack fulfillment, expiry, pricing, or the Telegram feed.

## Technical impact

- `services/v3/store.py`: `has_completed_topup_this_month(user_id)` reads
  `topup_purchases` for a completed purchase in the current billing month.
- `services/v3/web_music_charge.py`:
  - `WebMusicChargeBridge.charge(..., model=...)` calls
    `_enforce_free_model_scope()` after the period grant is ensured and the quote
    is resolved, before the wallet debit.
  - Free-plan detection uses `resolve_charge_plan()` (name `Free` or price 0).
  - `model_allows_free_grant()` is pure and unit-tested.
- `services/web_music_service.py`: the requested model is threaded from
  `generate()` → `_reserve_daily_slot()` → the charge bridge.
- No schema change; no Alembic migration.

## Files touched

- `platform_api/services/v3/store.py`
- `platform_api/services/v3/web_music_charge.py`
- `platform_api/services/web_music_service.py`
- `platform_api/tests/test_web_music_free_model_scope.py`
- `platform_api/CHANGELOG.md`
- `docs/changelog/2026-10-21-web-music-free-model-scope.md` (this file)

## Migration / deploy

- No migration. Deployed to sandbox with `sync_platform_api_sandbox.py`
  (API healthy, invariants OK). Production is pending an explicit deploy.

## Tests

- `python -m pytest tests/test_web_music_free_model_scope.py` → 3 passed.
- `python -m pytest tests/test_web_music_free_model_scope.py
  tests/test_v3_credits_only.py tests/test_web_music_generate_queue.py` →
  26 passed.

## Follow-ups

- Add the model lock to the `music_web` selector (currently the API rejects with
  a clear message; the selector still offers all models).
- The V2 fallback charge path (`_reserve_via_credits`) is not model-scoped; it is
  inactive while `credits_only_v3_charge` is On (production and sandbox).
- If the plan is later changed from 50/month, the Free model restriction follows
  the plan row automatically.
