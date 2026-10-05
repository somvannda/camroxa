# Music provider is a real AI Routing switch (Suno ↔ Camxora Music API)

## Summary

`music` was the one AI Routing operation that was not actually switchable. The
admin could store `camxora_music_api` pricing rows, but the provider could not be
selected in AI Routing (the request schema rejected it), the web Create charge
hard-coded the `suno` price, and generation always used the `suno` key pool. So
a pool switched to `musicapi` still charged **15 credits** instead of **10**.

This change makes AI Routing the single switch for the `music` operation:

- The admin can pick **Suno** (sunoapi.org) or **Camxora Music API** (musicapi)
  under **Settings → AI Routing → Music Generation**.
- The selected provider drives **both** the credit price and the key pool/host
  used to generate.
- Suno = 15 credits, Camxora Music API = 10 credits.

## Product impact

- Web Create on `music.camxora.com` charges 10 credits per generation when the
  routed music provider is Camxora Music API, and 15 when it is Suno. The
  create-button label and wallet debit now agree.
- Desktop batch/album pricing uses the same routed provider (it already read the
  routing assignment; it now resolves correctly for both providers).
- Admin **Settings → AI Routing** lists Camxora Music API for Music Generation
  once that provider has active keys in the Key Pool, and the copy explains the
  price difference.

## Technical impact

- `platform_api/clients/suno_routing.py`: add `SUNO_COMPATIBLE_PROVIDERS`,
  `DEFAULT_MUSIC_PROVIDER`, `normalize_music_provider`, and
  `is_suno_compatible_provider`.
- `platform_api/models/ai_routing_schemas.py`: allow `camxora_music_api` in the
  provider pattern (same class of gap as the earlier `kie` fix).
- `platform_api/services/ai_routing_service.py`: `save_assignments` no longer
  writes a `sub_model` for music for any provider.
- `platform_api/services/v3/list_prices.py`: `music` lookups accept a routed
  `music_provider`; `resolve_all_op_list_credits` / `resolve_op_list_units` take
  it and prefer `<provider>/music` before the static fallback.
- `platform_api/services/v3/credits_only_billing_service.py`: resolve the routed
  `music` provider once per quote / op-list and pass it through. A routing miss
  (or a provider without active keys) falls back to the static chain so pricing
  and plan pages never hard-fail.
- `platform_api/dependencies.py`: inject `get_ai_routing_service()` into
  `get_v3_billing_service()`.
- `platform_api/services/generation_service.py`: `_call_suno`,
  `poll_suno_generate_status`, `generate_suno_lyrics`, and `_call_suno_lyrics`
  select the routed provider's key-pool wrapper (lazily built for
  `camxora_music_api`). The legacy `_suno_pool_wrapper` stays the `suno` path.
- `platform_api/services/key_pool_service.py`: publish the active base URL for
  any Suno-compatible provider (not just `suno`).
- `platform_api/services/suno_audio_resolver.py`: `active_music_provider` reads
  `ai_routing_assignments` directly (so workers/callbacks resolve the same
  switch), and `active_suno_key_values` / `_active_suno_base_url` are
  provider-scoped.
- `platform_api/migrations/versions/131_camxora_music_api_music_default.py`: add
  the provider-wide `camxora_music_api / music` row (10 credits) that the
  no-sub-model billing lookup needs; migration 128 only seeded per-model rows.
- `admin_portal/src/pages/settings/ai-routing-section.tsx`: provider labels use
  `providerLabel` and the Music Generation copy describes the provider choice
  and prices.

## Files touched

- `platform_api/clients/suno_routing.py`
- `platform_api/models/ai_routing_schemas.py`
- `platform_api/services/ai_routing_service.py`
- `platform_api/services/v3/list_prices.py`
- `platform_api/services/v3/credits_only_billing_service.py`
- `platform_api/dependencies.py`
- `platform_api/services/generation_service.py`
- `platform_api/services/key_pool_service.py`
- `platform_api/services/suno_audio_resolver.py`
- `platform_api/migrations/versions/131_camxora_music_api_music_default.py`
- `admin_portal/src/pages/settings/ai-routing-section.tsx`
- `scripts/deploy/set_suno_pool.py` (now takes `--provider suno|camxora_music_api`)
- tests: `test_v3_credits_only.py`, `test_ai_routing_providers.py`,
  `test_suno_audio_resolver.py`

## Migration / deploy

1. Deploy `platform_api` and run `alembic upgrade head`
   (`131_camxora_music_api_music_default`) on sandbox, then production.
2. Rebuild `admin_portal` so the Music Generation provider list/copy shows
   Camxora Music API.
3. Restart `camxora-api` and the workers.
4. **Ops (required to charge 10):** in **Key Pool → Camxora Music API**, add the
   musicapi keys and set the active upstream host; then set **Settings → AI
   Routing → Music Generation → Camxora Music API**. Until that routing change,
   the routed provider stays Suno and 15 credits is charged. CLI equivalent for
   the pool step:
   `python scripts/deploy/set_suno_pool.py --env production --provider camxora_music_api --key "label=sk_..." --base-url https://musicapi.camxora.com`.
5. Verify: generate one web song and confirm the wallet debit and create-button
   label are 10 credits.

## Notes / trade-offs

- The routed provider is read per request, so a switch affects in-flight tasks —
  the same behavior as the previous `suno` pool base-URL toggle. `suno_tasks`
  does not stamp the provider on the row.
- The price follows the routing provider only. Pricing rows themselves stay per
  provider on the Credits page.

## Tests

- `python -m pytest platform_api/tests -q` → 3085 passed, 1 pre-existing failure
  (`test_desktop_release_upload.py::test_list_installers_returns_newest_first`,
  Windows mtime sort, unrelated).
- Targeted billing/routing/resolver/generation/key-pool subset → 729 passed.

## Follow-ups

- Decide whether to stamp `suno_tasks.provider` so a provider switch does not
  affect in-flight polling.
- Consider a routing fallback (Suno → Camxora) if clean failover between the two
  resellers is wanted.
