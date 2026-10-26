# Suno Studio Operations — Credit Charge Report

Measured on 2026-10-26 against the Premier account `iamduke1987@gmail.com`.
All balances are Suno account credits from the account billing endpoint.

- Starting balance: **2,620**
- Ending balance after the measured operations: **2,520**
- Total measured spend: **100 Suno credits**

## Measured charges

| Operation | Suno request | Clips returned | Suno credits charged |
|---|---|---:|---:|
| Extend | `extend` | 2 | **10** |
| Stems — Vocals + Instrumental | `stems` / `vocal` | 4 | **10** |
| Stems — Full stems | `stems` / 12-track | 24 | **50** |
| Cover | `cover` | 2 | **10** |
| Add vocals | `overpainting` | 2 | **10** |
| Replace section (30 seconds) | `infill` | 2 | **10** |
| Add instrumental | `overpainting` | — | **not measured** |

## Observations

- A normal two-clip edit batch costs **10 Suno credits**.
- Extend, Cover, Add vocals, and a 30-second Replace section all landed at
  **10 credits**.
- The two-track Stems operation also costs **10 credits**, but returns
  four clips (two vocal and two instrumental variants).
- The 12-track Stems operation costs **50 credits** and returns 24 clips
  (two sets of 12).
- Add instrumental uses the same underlying Suno `overpainting` task as
  Add vocals; it should be 10 credits, but it was not separately measured.
- Replace-section pricing may depend on section length or selected region.
  Only a 30-second section was measured.

## Test limitation

The local musicapi instance had no B2/S3 object storage configured for these
measurements. Extend, Cover, Add vocals, and Replace section generated clips at
Suno, but the musicapi job ended with `media_storage_not_configured`. Suno still
charged the credits. Stems completed successfully because its result did not
require the same local media storage path.

This is a local environment gap, not a platform API or Suno routing gap.
Production must have durable storage configured before treating these
operations as successful.

## Pricing implication

Do not hardcode a Camxora price from this report. Use the existing pricing
table and apply the intended margin.

A minimum-cost baseline before markup:

```text
Extend                10 Suno credits
Cover                 10 Suno credits
Add vocals            10 Suno credits
Add instrumental      10 Suno credits (verify)
Replace section       10 Suno credits baseline (verify length behavior)
Stems — 2 track       10 Suno credits
Stems — 12 track      50 Suno credits
```

The 12-track Stems operation is five times the cost of the other measured
operations and should be priced separately rather than sharing a flat Studio
operation price.

## Caveats

- One Premier account and one plan on one date.
- Suno may change pricing, run promotions, or vary cost by plan, clip length,
  model, or region.
- The 12-track operation returns two full stem sets; product UX should decide
  whether to present all 24 clips or select one set.
- Add instrumental and longer Replace-section ranges still need measurement.

## Cleanup performed

- Synthetic platform task deleted.
- Test `studio_operations` rows deleted.
- Test Studio cloud project deleted.
- Test `asset_owners` mapping removed.
- Local test `env-seed` account removed and remaining local accounts deactivated
  with cookies cleared.
- Local musicapi studio test jobs deleted.
- musicapi stopped.
- Platform API restarted without the test token or local musicapi URL.
- Temporary JWT/captcha files removed.
- Extra browser tabs closed.

No production build, push, or deploy was performed.
