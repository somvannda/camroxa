# Telegram ops activity feed

**Date:** 2026-08-18  
**Surfaces:** `platform_api`  
**Branch:** `feature/telegram-ops-alerts`

## Summary

Ops can watch a Telegram group for every new signup, paid subscription/checkout, and credit burn (music, lyric, and every other billed activity), labeled **FREE** vs **PAID**. The feed is noisy on purpose until the free-credit abuse picture is stable; it can be switched off without a code change.

## Product impact

- No customer-facing UI.
- A Telegram group receives live messages for:
  - new account signup
  - paid studio checkout (plan / credit pack / add-on) and web-music subscription activate/renew when those modules are loaded
  - every wallet credit spend and refund
  - studio plan-quota use (paid users, 0 wallet)
  - web-music daily-free and subscription credit consume/refund (via startup hook on the v2 credit service when present)
- Each spend line includes activity (music / lyric / image / video / …) and FREE vs PAID.

## Technical impact

- Env: `PLATFORM_TELEGRAM_BOT_TOKEN`, `PLATFORM_TELEGRAM_CHAT_ID`, `PLATFORM_TELEGRAM_OPS_ENABLED` (default true).
- Soft kill-switch (no restart): `system_settings.telegram_ops_alerts_enabled=false` (cached ~15s).
- Hard kill-switch: `PLATFORM_TELEGRAM_OPS_ENABLED=false` then restart `camxora-api` (and workers).
- Posts are fire-and-forget; Telegram failures never fail signup, pay, or generate.
- In the ops group, `/stats` and `/burncredit` use stacked period rows (Today / Yesterday / Last 7 Days / Last 30 Days) so Telegram mobile can read them. `/burncredit` shows songs · credits and USD at $0.06 per request. Daily post at **10:00 PM Asia/Phnom_Penh**.
- Web-music v2 files are not in `main`; hooks wrap those classes at process start if they already exist on the server.

## Files touched

- `platform_api/config.py`
- `platform_api/services/telegram_ops_alert_service.py`
- `platform_api/main.py`
- `platform_api/worker.py`
- `platform_api/tests/test_telegram_ops_alert_service.py`
- `scripts/deploy/configure_telegram_ops_sandbox.py`
- `scripts/deploy/hotfix_telegram_ops_sandbox.py`

## Migration / deploy

No migration.

1. Create a Telegram bot with [@BotFather](https://t.me/BotFather), add it to the ops group, disable privacy mode (`/setprivacy` → Disable) so it can post, and copy the group chat id (negative number, often `-100…`).
2. Put token + chat id in `.deploy/secrets.sandbox.env`:
   - `TELEGRAM_BOT_TOKEN=...`
   - `TELEGRAM_CHAT_ID=...`
3. Deploy sandbox API, then run `python scripts/deploy/configure_telegram_ops_sandbox.py` (writes remote `.env`, restarts API, sends a test ping).
4. Production (2026-08-18, explicit request): file-scoped hotfix of the notifier + `config.py` Telegram settings, locked to group `Camxora Activities` (`-5585173503`).

Turn off later (sandbox SQL, no restart):

```sql
INSERT INTO system_settings (key, value, value_type, updated_at)
VALUES ('telegram_ops_alerts_enabled', 'false', 'boolean', NOW())
ON CONFLICT (key) DO UPDATE
SET value = 'false', value_type = 'boolean', updated_at = NOW();
```

## Tests

- `platform_api/tests/test_telegram_ops_alert_service.py`: activity classification, HTML escaping, FREE badge, no-op without token, sendMessage payload, idempotent v2 hook install.

## Follow-ups

- Production env + bot (separate token/chat if desired).
- After abuse is under control, flip the kill-switch or stop posting every spend and keep signup/pay only.
