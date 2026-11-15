# Studio: the "Chorus" plugin was really Rhythm Gate

**Date:** 2026-11-14
**Surfaces:** camxora.com (Studio plugin dock), musicapi codec, docs
**Status:** fixed locally, gates green, not deployed

## Finding

The plugin catalog mapped version id `537ba288-f700-4c96-b103-c84e2b62fab6` to a
local **Chorus**, sourced from the bundle registry. Resolving that id against the
live plugin registry (`GET /api/plugins/version/{id}`) returns **Rhythm Gate**:

```
name: Rhythm Gate
parameters: attack 0.01–0.45 (default 0.12), depth 0–1 (0.75),
            mix 0–1 (0.65), rate ∈ {1/16, 1/8, 1/4}, release 0.01–0.45 (0.22)
```

No Chorus plugin exists in the account's plugin catalog or in any project chain.
The local effect therefore both rendered the wrong thing and wrote a Rhythm Gate
with chorus-shaped parameters (including an invalid `1/2` rate that Suno merely
echoed back in an earlier probe).

## Fix

- Local plugin renamed to **Rhythm Gate** (`pluginId: "rhythmGate"`) with the
  live controls: rate as a `1/16`/`1/8`/`1/4` select, depth/mix 0–1, attack and
  release. `ParamDef` gained `choices`, rendered as a select in the dock.
- Audio approximation: a square-LFO gain gate (1/4 = 2 Hz, 1/8 = 4 Hz, 1/16 = 8 Hz
  at 120 BPM); attack/release shape Suno's envelope and are not rendered, so the
  card is marked approximate.
- Codec: `SUNO_PLUGIN_CATALOG.rhythmGate` maps attack/depth/mix/release by name
  and rate index ↔ the division enum. The Hz/division converters are gone.
- Persisted `chorus` chain entries migrate to `rhythmGate` (depth/mix 0–100 → 0–1,
  rate Hz → nearest allowed division) instead of being dropped.
- Help entry, preview path and docs updated; the old `unverified` badge is gone
  because the controls now come from the live descriptor.

## Verification

| Gate | Result |
|---|---|
| web typecheck / `check:ui` | clean |
| Vitest | **339 passed** (new migration + clamp tests) |
| musicapi codec tests | **33 passed** |
| Playwright (plugins, designer, learn, catalog dialog) | **6 passed** |
| Live registry probe | 15 distinct version ids resolved; all other built-ins matched their catalog names |
