# platform_api: Telegram spend feed badges pack buyers as PAID

## Summary

The ops feed showed `🔥 SPEND · FREE · Production` for a Free-plan user who had
just bought a credit pack, even though every generation charged 10 credits from
purchased balance. `_user_snapshot()` only treated an active web subscription or
an active studio licence as `PAID`, so a completed one-off pack fell back to
`FREE`.

A pack is a payment: it also unlocks V6-Pro / V6-Wild for the calendar month
(`WebMusicChargeBridge.premium_unlocked()`), so its generations are paid usage.

- Free plan, no pack → `FREE`.
- Free plan, completed pack this month → `PAID`.
- Active web subscription or studio licence → `PAID` (unchanged).

## Technical impact

- `services/telegram_ops_alert_service.py`
  - `_account_status()` is now a pure helper covering web subscription, studio
    licence and pack purchase; it is unit-tested directly.
  - `_user_snapshot()` adds
    `has_pack_this_month` to its single round trip:

    ```sql
    EXISTS(
      SELECT 1 FROM topup_purchases t
      WHERE t.user_id = u.id
        AND t.payment_status = 'completed'
        AND COALESCE(t.completed_at, t.created_at) >= date_trunc('month', NOW())
    )
    ```

- No schema change and no new query round trip.
- The 30s snapshot cache is unchanged, so the badge catches up within 30s of a
  pack completing.

## Tests

- `python -m pytest platform_api/tests/test_telegram_ops_alert_service.py -q`
  → 33 passed.

## Deploy

- `platform_api` API only; restart `camxora-api.service` (workers do not render
  the badge). No migration.

## Notes

- Purchased and granted credits share one wallet, so the badge is account-level
  (purchased this month), not a per-debit source tag. That matches the premium
  unlock rule exactly.
