# v3 image charges follow AI Routing again

**Branch:** `fix/v3-image-routing-price`

## Symptom

A desktop background image billed **60 credits** (`reason: v3_image`, pool
`studio wallet`) while Admin → Credits showed the routed model
`slai / cx/gpt-image-2.5 / Background Image` at **6 credits**.

## Root cause

`music` became a real AI Routing switch on 2026-10-05: the routed provider
(`suno` / `camxora_music_api`) decides which pricing row is charged. `image`
never got that treatment.

`platform_api/services/v3/ops.py` priced `image` with a provider-blind chain:

```python
"image": (("fal", "background_image"), ("openai", "background_image")),
```

Production routes `background_image` and `thumbnail_image` to
`slai / cx/gpt-image-2.5`, so neither named lookup matched (the SLAI rows carry
`sub_model = 'cx/gpt-image-2.5'`, and `get_price(service, op, None)` only finds a
provider-wide default row). `resolve_op_list_units()` then fell through to
`_scan_pricing_units()`, which returned the **first** row whose
`operation_type` was `background_image`, `thumbnail_image`, or `image` — in
`get_all()` order, i.e. alphabetically by provider, so `fal` beat `slai`.

The v3 charge path uses the same resolver for the preflight/hold and for the
debit, so the wrong row was charged consistently and nothing looked like an
error in the logs.

## Fix

- `PRICING_FALLBACKS` entries are now `(ai_service, operation_type, sub_model)`.
- `_image_fallbacks()` mirrors `_music_fallbacks()`: the routed provider and
  routed `sub_model` are tried first, then that provider's
  `background_image` / `thumbnail_image` defaults, then the static chain.
- `background_image` and `thumbnail_image` are separate routing assignments but
  bill the one `image` op, so `quote` / `charge` / `refund` accept an optional
  `operation` (the concrete v1 operation). `_charge_via_v3` forwards it, so a
  thumbnail is priced from the thumbnail assignment. Without it the background
  image assignment is used.
- `_scan_pricing_units()` is now two-pass (routed provider first, any provider
  second), tries the concrete operation name before aliases, and logs a warning
  when it has to take another provider's row.
- `/api/v3/billing/{quote,charge,refund}` accept the optional `operation` field.
- `refund` now writes the normalized op (`v3_refund_image`) into the ledger
  reason and metadata; it previously wrote the raw `operation` parameter, which
  is `None` for every existing caller.

## Verification

```
python -m pytest tests/test_v3_credits_only.py tests/test_v3_generate_charge.py -q
# 28 passed

python -m pytest tests -q -k "v3 or image or pricing or enforcement or soft_overage or web_music_v3 or billing"
# 295 passed, 2910 deselected
```

New tests assert the routed SLAI price (6) wins over a stale FAL row (60), that
a thumbnail bills its own assignment, that the charge debits the routed price,
that the scan prefers the routed provider, and that a routing miss still falls
back to the static chain.

## Post-deploy check

1. Confirm the stale row (read-only):
   `scripts/deploy/diag_prod_image_pricing.py`
2. Generate one background image and confirm the debit is 6 credits and the
   Telegram spend line shows the SLAI price.
3. Charges already taken at the wrong price are not refunded automatically.
   Refund the difference with the v3 refund path and a stable `ref_id`
   (`scripts/deploy/refund_v3_image_overcharge.py --apply`).
