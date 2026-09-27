# Web music generation gated by credits, not a per-IP daily cap

**Date:** 2026-09-27
**Branch:** `fix/music-web-credit-gated-generation`
**Surfaces:** platform_api
**Status:** implemented (sandbox)

## Summary

Paid users — and any user holding credits — were capped at **5 songs per day**
across `/api/v3/web-music/generate`. The cap was an **IP-scoped farm guard**
(`abuse_detection.MAX_GENERATIONS_PER_IP_PER_DAY = 5`) with no knowledge of plan
or credit balance, so everyone behind a shared egress IP (offices, mobile
carriers, families) shared one 5/day budget and got HTTP 429 `IP_DAILY_LIMIT`
even after paying.

Generation is now gated by the credit balance. A user who can pay for a song
(active paid web subscription, active desktop Pro license, or a positive
spendable credit wallet — including the Free daily grant) is exempt from the
per-IP daily cap and can generate as many songs as their credits allow. The
signup-farm caps are unchanged.

## Product impact

- Paid users no longer see `Maximum 5 free songs per day from one network`.
- Free users holding credits (e.g. the daily free grant) can generate until
  their credits run out; the credit charge is the gate.
- The per-IP daily cap now applies only to accounts with nothing to spend, and
  its message says credits are required.
- Signup-abuse protection is untouched: 3 accounts/IP/hour, 5/IP/day, plus the
  signup-farm generation freeze.

## Technical impact

- `PlatformAPI` `POST /web-music/generate` now resolves a `credited` flag before
  the abuse check and passes it to `track_generation_attempt`.
- `check_ip_abuse(..., event_type="generation", credited=True)` returns before
  incrementing `abuse:ip_daily:{ip}:{day}`, so credit-funded users never consume
  or trip the shared per-IP budget. `quota_hit` / `account_creation` paths are
  unchanged.
- New `WebMusicService.has_generation_credits(user_id)` centralises the
  paid/credit check for both the V3 credits-only path
  (`spendable_credits` → `paid_web or spendable > 0`), the V2 fallback
  (`total_available > 0` or subscription), and the Pro license check. It fails
  closed (returns `False`) if the lookup errors, preserving the prior behaviour.
- Per-user burst limiting (`web_music_generate`, 40/60s) and generation-freeze
  checks are unchanged.

## Files touched

- `platform_api/middleware/abuse_detection.py`
- `platform_api/routers/web_music.py`
- `platform_api/services/web_music_service.py`
- `platform_api/tests/test_abuse_detection.py`

## Migration / deploy

- No DB migration, no settings change.
- Deploy: `python scripts/deploy/sync_platform_api_sandbox.py` (restarts
  `camxora-api`). Sandbox first; production only on explicit request.

## Tests

- `platform_api/tests/test_abuse_detection.py` — uncredited users still 429;
  credited users are exempt past 3× the cap.
- Related suites pass: `test_web_music_router.py`, `test_web_music_credit_hardening.py`,
  `test_web_music_v3_charge.py`, `test_web_music_generate_queue.py`.

## Follow-ups

- Sandbox paid plans set `daily_song_limit_per_channel = 7` vs prod 999. This is
  **not** the reported 5/day cap: the web-music generate route never calls
  `_enforce_plan_quotas`, and subscription plans bypass the daily quota via
  wallet credits (`_can_wallet_daily_bypass`). No action needed for this fix;
  the sandbox/prod drift is only worth aligning for consistency.
- Frontend `mergeV3CreditBalance(v3, null)` mis-derives `topup_credits` and
  `daily_free_*` because the V2 wallet is only fetched when the V3 call throws.
  `total_credits` is correct (V3 `wallet_view` reads the shared `credit_wallets`
  table), so this is display-only.
- Legacy settings `web_music_free_daily_limit = 5` / `web_music_free_daily_credits = 50`
  are now redundant with credit gating. Retired in
  `docs/changelog/2026-09-27-retire-web-music-free-daily-settings.md`.
