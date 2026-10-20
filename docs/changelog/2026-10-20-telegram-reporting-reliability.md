# Ops Telegram: token leak, wrong burn numbers, and dropped reports

**Branch:** `perf/telegram-reporting`
**Date:** 2026-10-20

## Why

Production diagnosis of the ops channel (`Camxora Activities`, bot `@CamxoraBot`)
found four concrete problems:

- **The bot token was written to journald.** httpx logs every request URL at
  INFO, and the Telegram token is part of the path
  (`/bot<token>/sendMessage`, `/bot<token>/getUpdates`). Every API worker and
  job worker was retaining the live token.
- **The burn report was wrong.** `credit_transactions` mixes three writers:
  legacy studio rows in display credits, legacy web rows in display credits,
  and `v3_*` rows in micro-units, with both signs. `_WEB_CREDIT_SQL` filtered on
  `consumed_web_music%` (no longer written), so web burn was always **0**, while
  `_STUDIO_CREDIT_SQL` counted every v3 web charge as studio and divided legacy
  rows by 10,000.
- **Telegram dropped messages.** 566 HTTP 429s in 30 days (up to 33 s
  `retry_after`) were logged and discarded, plus 97 request timeouts. A fresh
  HTTPS client per message paid ~330 ms TLS from the VPS.
- **The daily 22:00 report was unreliable.** It sent on 16 of 30 days. The
  claim marker was written before sending with a 48 h TTL, so a restart at
  22:00 skipped the day. The command poller was split-brained: 5,540 HTTP 409
  conflicts because `_I_AM_POLLER` was sticky and the lock was renewed without
  checking ownership.

## Changes

### `fix(telegram): stop logging the bot token via httpx request URLs`
- `telegram_ops_alert_service.py`: `httpx` logger pinned to WARNING.

### `fix(telegram): attribute credit burn correctly and use index-friendly windows`
- One `_BURN_SQL` classifies rows into `web` / `studio` / `unattributed`:
  - web = legacy `consumed_web_music%` **or** a v3 music debit whose
    `ref_id` is a platform `suno_tasks.id` (proven, not guessed);
  - studio = other v3 rows and legacy `<op> via <provider>` rows;
  - everything else (image/lyric/title shared by both products, net refunds)
    is reported separately instead of inflating studio.
- Normalises scale per family (display credits vs micro-units) and uses
  `ABS(amount)` with direction, so refunds subtract correctly.
- Day windows are now `created_at >= …` range predicates, not
  `(created_at AT TIME ZONE …)::date` casts.
- Daily report gains `new users today`, `songs today` and
  **platform revenue today / 7d** from `billing_payments` (platform billing
  only; web-music revenue lives in musicapi).

### `fix(telegram): single-owner poller, ownership-safe lock, crash-safe daily report`
- Lock renew/release use compare-and-swap Lua with a per-process
  `pid:uuid` token; HTTP 409 drops leadership; Redis errors fail **closed**.
- Offset is kept in memory when Redis is unavailable (no replay loop).
- Daily report claims `"sending"` for 10 minutes, marks the day only after a
  successful post, deletes the claim on failure, and retries every 60 s.
- New `PLATFORM_TELEGRAM_POLLER_ENABLED` (default `true`); worker units set it
  to `false` so only the API process polls.

### `perf(telegram): pool the HTTP client, retry 429s, batch bursts, drain on shutdown`
- Process-wide keep-alive `httpx.AsyncClient`.
- Sends spaced ~2.5 s apart; 429 honours `retry_after` (capped at 10 s) and
  retries once; 5xx retries once.
- `spend` and `download` events are coalesced over a 2 s window into one
  message; signups/logins/payments/refunds/alerts stay immediate.
- Long reports are split on line boundaries instead of truncated at 4,000.
- User snapshot is one query with a 30 s cache.
- Pending posts are flushed on shutdown (`drain_telegram_ops`).

### `feat(telegram): indexes for report windows`
- Migration `139_telegram_report_indexes` adds `created_at` indexes on
  `users`, `suno_tasks`, `credit_transactions`, and a partial
  `billing_payments(fulfilled_at)` index.

## Action required (production)

1. **Revoke and reissue the bot token** with @BotFather — the old token is in
   retained journals. Then update `PLATFORM_TELEGRAM_BOT_TOKEN` and remove old
   journal history if required by policy.
2. Apply migration `139` (`alembic upgrade head`).
3. Deploy; worker units now receive
   `PLATFORM_TELEGRAM_POLLER_ENABLED=false`.
4. Confirm one leader: `redis-cli -n 1 get telegram:ops:poller` should hold a
   single `pid:uuid` value, and `journalctl -u camxora-api | grep "status=409"`
   should stay empty.

## Tests

`python -m pytest platform_api/tests/test_telegram_ops_alert_service.py` —
26 tests covering attribution SQL, the shared bucket, daily claim/failure/
in-progress recovery, 429 retry, chunking, and formatting.
