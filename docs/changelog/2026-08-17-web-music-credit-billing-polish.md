# Web Music — Simple-mode lyrics billing + yearly monthly credit reset

**Date:** 2026-08-17  
**Surfaces:** `platform_api`  
**Branch:** `feature/web-music-credits-hardening`

## Summary

Two credit-system polish items:

1. **Simple mode lyrics** — Suno lyrics generation is included in the 10-credit song charge, but credits are now reserved *before* the lyrics call so zero-credit users cannot consume Suno API quota for free.
2. **Yearly plans** — Monthly credit allowance now refreshes every 30 days while billing stays on the yearly cycle (unused monthly credits still do not roll over).

## Changes

### Simple mode (`web_music_service.generate`)
- Validate inputs, then charge 10 credits, then call `generate_suno_lyrics`.
- Refund on lyrics failure before Suno submit.
- Advanced mode **Auto-generate lyrics** (`generate_draft`) remains separately credit-priced via the text LLM route.

### Yearly subscription credit cadence (`subscription_service`)
- `reset_quota_if_needed()` handles yearly mid-cycle refreshes via `last_credit_reset`.
- Background job picks up yearly subs due for monthly allowance refresh.
- `reset_at` in balance APIs uses next 30-day refresh for yearly subs.

## Test plan
- `pytest platform_api/tests/test_web_music_subscription_credit_reset.py`
- Simple mode with 0 credits → rejected before Suno lyrics API call
- Yearly subscriber after 30+ days → `monthly_credits_used` reset, billing period unchanged
