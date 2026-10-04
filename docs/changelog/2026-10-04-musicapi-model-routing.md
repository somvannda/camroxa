# musicapi: chirp-goose runs on free accounts, everything else is paid-only

## Summary

Account routing defaults were inconsistent: `chirp-auk-turbo` preferred free
accounts, `chirp-crow`/`chirp-fenix` were paid-only, and **every other model —
including the free-tier `chirp-goose` (V6-Mini) and the premium V6 models — was
`any`**, so a request could land on a free or paid account depending on health,
not on the model. This sets an explicit default: `chirp-goose` prefers free
accounts; every other model is paid-only.

## Product impact

- **`chirp-goose` (V6-Mini)** — the free/efficient model — is served by free
  accounts first, keeping cheap generations off paid quota. It still falls back
  to a paid account when no free one is healthy (`prefer_free`, not strict).
- **Every other model** (V6 `chirp-hawk`, `chirp-hawk-wild`, crow/fenix, etc.)
  uses a **paid account only**, so premium generations never consume a free
  account (which cannot serve them) and paid quota is reserved for premium work.
- Requests without a model route the same way — the default model is premium, so
  they are paid-only.
- Retired keys that normalise onto the mini model (`v6-mini`, `v3-5`, `v3`, …)
  now route as `chirp-goose` instead of falling through to the old `any` default.
- Admin `routing_rules` still wins, and is now looked up on the **normalised**
  model so a rule keyed on `chirp-goose` matches aliases too.

## Technical impact

- `src/models.ts`: new pure, exported `defaultRoutingPolicy(model)` →
  `prefer_free` for normalised `chirp-goose`, else `paid_only`. Exported so it is
  unit-testable without a pool/DB.
- `src/server.ts`:
  - `routingPolicy()` normalises the model, looks up `routing_rules` on the
    normalised key, then falls back to `defaultRoutingPolicy()` (drops the
    `chirp-auk-turbo`/`chirp-crow`/`chirp-fenix` special cases and the `any`
    default).
  - The three `model ? await routingPolicy(model) : "any"` call sites now always
    call `routingPolicy(model)`, so model-less requests also get the default.

No schema change; `routing_rules` still overrides.

## Files touched

- `musicapi/src/models.ts`
- `musicapi/src/server.ts`
- `docs/changelog/2026-10-04-musicapi-model-routing.md` (this file)

## Migration / deploy

- No migration. Deploy via the normal sandbox-first chain. If any `routing_rules`
  rows exist for models that should now be paid-only, remove them so the new
  default applies (admin panel → Routing).

## Tests

- `npm run typecheck` → clean.
- Unit probe of `defaultRoutingPolicy` (13 cases) → all pass: `chirp-goose`,
  `v6-mini`, `V6_MINI`, `v3-5`, `chirp-v3` → `prefer_free`; `chirp-hawk`,
  `chirp-hawk-wild`, `chirp-auk-turbo`, `chirp-crow`, `chirp-fenix`, `v6`,
  `undefined` → `paid_only`. Temp harness removed after.

## Follow-ups

- A strict `free_only` policy (never touch paid for chirp-goose) would need a new
  policy value; today `prefer_free` falls back to paid when no free account is
  available.
