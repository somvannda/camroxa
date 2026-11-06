# Music price follows the routed provider: 15 on sunoapi.org, 10 on musicapi

**Date:** 2026-11-05
**Decision:** the music price is **not** uniform. It follows whichever provider
AI Routing picked:

| Provider id | Upstream | Price per generation |
|---|---|---|
| `camxora_music_api` | Camxora musicapi | **10 credits** |
| `suno` | sunoapi.org reseller | **15 credits** |

Both ids are served by the same Suno-compatible client; only the upstream host
and the `credit_pricing` row differ. This supersedes migration 176 (10 for Suno)
because the reseller's cost is higher and must not be sold at the musicapi price.

## What changed

| File | Change |
|---|---|
| `platform_api/migrations/versions/182_music_price_by_provider.py` | `suno` music = 150,000 units (15 cr); `camxora_music_api` music = 100,000 (10 cr), all sub-models |
| `platform_api/services/pricing_sync_service.py` | routing-sync suggestions are provider-aware (suno 15/cost 12, musicapi 10/cost 6) |
| `platform_api/models/products.py` | `WEB_MUSIC_CREDITS_PER_SONG` stays **10** (musicapi default / refund floor) |
| `platform_api/services/pricing_display.py` | `DEFAULT_CREDITS_PER_GENERATE` stays **10** (display fallback; quotes read the row) |
| `platform_api/services/ai_routing_service.py` | explicit validation that the `music` assignment is a music provider |
| Admin daily-cap copy | "10 credits on our musicapi (15 on the reseller)" |

## Why the constants stay at 10

`WEB_MUSIC_CREDITS_PER_SONG` is only a fallback for legacy v2 paths. The v3
charge/refund path uses the quoted amount, so a 15-credit reseller song is
charged and refunded exactly. Keeping the constant at the **cheaper** provider
means a legacy refund can never mint credits (refunding 15 after a 10 charge
would be exploitable).

## Failover: chain + settlement

Because the price differs, failover settles on the provider that **executed**:

- `ai_routing_music_fallback_chain` orders the providers (default: musicapi, then
  sunoapi.org). Entries are filtered by active keys.
- Billing and execution both use `resolve_music_chain("music")[0]`, so a manual
  switch and the no-keys fallback are price-correct.
- Desktop `POST /generation/suno` and batch submission pass
  `allow_music_failover=True`: `_call_suno_with_provider` advances on provider
  failure and reports the executed provider, then
  `UsageEnforcementService.settle_music_price` charges or refunds the 15-vs-10
  difference. A delivered song is never failed because the delta failed — the
  shortfall is logged.
- Web Create stays single-provider (no failover) until it passes a settle
  callback, so it cannot undercharge.

## Ops prerequisite

To make the split real, each id needs its own key and host:

| Provider id | Key `base_url` | Role |
|---|---|---|
| `camxora_music_api` | `https://musicapi.camxora.com` | normal operation (10) |
| `suno` | `https://api.sunoapi.org` | reseller fallback (15) |

Today only `suno` has an active key, with `base_url = http://127.0.0.1:4003`
(our local musicapi), and `camxora_music_api` has none — so the ids are
inverted until the keys are re-pointed.
