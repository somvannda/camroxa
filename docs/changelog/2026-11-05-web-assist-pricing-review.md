# Web AI-assist pricing reviewed; unreviewed prices can no longer be charged

**Date:** 2026-11-05

## What changed

| File | Change |
|---|---|
| `platform_api/migrations/versions/183_web_assist_pricing_review.py` | the four `web_music_*` rows become **5 credits** with a registry-estimated cost basis and `needs_review = false` |
| `platform_api/services/credit_pricing_service.py` | `lookup_pricing_entry` / `get_price` raise `PRICING_NEEDS_REVIEW` for draft rows; `allow_draft=True` opt-out |
| `platform_api/services/v3/list_prices.py` | the last-resort price scan skips draft rows |

## Why

The four rows were auto-seeded drafts at 2–3 credits with a zero cost basis, and
until W5b they were never selected (the quote scanned into the desktop `lyric`
row instead). Now that the quote is routing-aware, they are the real price, so a
draft is no longer acceptable.

5 credits matches `docs/credits-only-plan-unification.md`
("Lyrics assist = `lyric`; Style = `style`", AI assist 5 credits).

## Behaviour

- Web lyric/style assist: **5 credits** (was effectively ~0.02 by scan order).
- Desktop text operations are unaffected by this migration (they use the
  `lyric`/`title`/`album` rows).
- Any pricing row still flagged `needs_review` now **cannot** be charged; the
  error is actionable (`code = PRICING_NEEDS_REVIEW`). Admin pages still list
  and approve them.
