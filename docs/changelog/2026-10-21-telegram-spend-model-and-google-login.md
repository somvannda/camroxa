# Ops Telegram: spend model + Google sign-in events

**Branch:** `feat/telegram-spend-model-login`
**Date:** 2026-10-21

## Why

- The SPEND feed showed credits and activity but not the Suno model, so ops could
  not tell a `v6 pro` generation from `v6 wild` or `v6 mini`. It also labelled
  every v3 charge as `pool: studio wallet`, including web-music charges
  (`metadata.product = web_music`).
- Google sign-in on `music.camxora.com` produced no LOGIN message. The LOGIN
  hook wraps `AuthService.authenticate` (password only); the Google callback
  issues a session without calling it.

## Changes

### Spend model + correct pool

- `CreditsOnlyBillingService.charge()` accepts `model` and stores it in
  `credit_transactions.metadata` (`V6`, `V6_WILD`, `V6_MINI`, …).
- Web music passes the model through `WebMusicChargeBridge`; the desktop/v1 path
  passes `sub_model` through `UsageEnforcementService._charge_via_v3`.
- `format_ops_message()` renders `model: <b>v6 wild</b>` (labels: `V6` → v6 pro,
  `V6_WILD` → v6 wild, `V6_MINI` → v6 mini, `V5_5` → v5.5, `V5` → v5).
- The wallet hook uses `metadata.product` to label the pool: `web music` for web
  music, `studio wallet` otherwise.

### Google sign-in

- `google_auth_callback` now emits `notify_login()` when an **existing** account
  signs in with Google. New accounts still emit only SIGNUP.

## Tests

```
python -m pytest platform_api/tests/test_telegram_ops_alert_service.py \
  platform_api/tests/test_v3_credits_only.py \
  platform_api/tests/test_web_music_v3_charge.py \
  platform_api/tests/test_v3_generate_charge.py -q
# 67 passed
```

## Deploy

- No migration.
- Deploy platform_api, restart; new SPEND messages include the model and the
  correct pool, and Google sign-ins for existing accounts emit LOGIN.
- Historical charges have no model in metadata; only new generations show it.
