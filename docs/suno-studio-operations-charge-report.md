# Suno Studio Operations — Credit Charge Report

Measured on 2026-10-26 against the Premier account `iamduke1987@gmail.com`.
All balances are Suno account credits from the account billing endpoint.

- Starting balance: **2,620**
- Ending balance: **2,500**
- Total measured spend: **120 Suno credits**

## Measured charges

| Operation | Suno request | Clips returned | Suno credits charged |
|---|---|---:|---:|
| Extend | `extend` | 2 | **10** |
| Stems — Vocals + Instrumental | `stems` / `vocal` | 4 | **10** |
| Stems — Full stems | `stems` / 12-track | 24 | **50** |
| Cover | `cover` | 2 | **10** |
| Add vocals | `overpainting` | 2 | **10** |
| Add instrumental | `overpainting` | 2 | **10** |
| Replace section — 30 seconds | `infill` | 2 | **10** |
| Replace section — 120 seconds | `infill` | 2 | **10** |

## Observations

- A normal two-clip edit batch costs **10 Suno credits**.
- Extend, Cover, Add vocals, Add instrumental, and Replace section all cost
  **10 credits**.
- The 2-track Stems operation also costs **10 credits**, but returns four clips
  (two vocal and two instrumental variants).
- The 12-track Stems operation costs **50 credits** and returns 24 clips
  (two sets of 12).
- Replace section costs **10 credits for both 30-second and 120-second
  ranges**. It appears to be priced per job, not per second, at least in the
  tested range.
- Suno returns two clips for a normal edit job. Product UX should decide
  whether to add both variants as lanes or select one.

## Test limitation

The local musicapi instance had no B2/S3 object storage configured for these
measurements. Extend, Cover, Add vocals, Add instrumental, and Replace section
generated clips at Suno, but the musicapi job ended with
`media_storage_not_configured`. Suno still charged the credits. Stems completed
successfully because its result did not require the same local media storage
path.

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
Add instrumental      10 Suno credits
Replace section       10 Suno credits
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
- Replace section was measured at 30 and 120 seconds on a 207-second source.
  Longer or full-length ranges may behave differently.
- These are Suno credits, not Camxora credits. Camxora pricing needs its own
  conversion and margin.

## Cleanup performed

- Synthetic platform task deleted.
- Test `studio_operations` rows deleted.
- Test Studio cloud project deleted.
- Test `asset_owners` mapping removed.
- Local test `env-seed` account removed and remaining local accounts deactivated
  with cookies cleared.
- Local musicapi studio test jobs deleted.
- musicapi stopped.
- Platform API running clean without the test token or local musicapi URL.
- Temporary JWT/captcha files removed.
- Extra browser tabs closed.

No production build, push, or deploy was performed.
