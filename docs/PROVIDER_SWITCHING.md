# Suno Upstream — single owner: `musicapi.camxora.com`

> **Status:** the reseller host is retired. This document used to describe a
> runtime switch between `sunoapi.org` (`apibox.erweima.ai`) and Camxora's own
> `musicapi`. That switch is no longer part of the product.

## Current routing

```
camxora.com / desktop / clients
        │
        ▼
platform_api                     PLATFORM_SUNO_API_BASE_URL
(provider pool, billing)  ──────▶ https://musicapi.camxora.com
        │
        ▼
musicapi                         SUNO_API_URL
(our wrapper)             ──────▶ https://studio-api-prod.suno.com
```

- `platform_api` talks to **our** musicapi. The default comes from
  `platform_api/config.py` (`suno_api_base_url = "https://musicapi.camxora.com"`)
  and must not be pointed anywhere else.
- `musicapi` talks to the **Suno interface directly**, authenticated with the
  pooled `__client` cookies (`musicapi/src/client.ts`), defaulting to
  `https://studio-api-prod.suno.com` (`musicapi/src/config.ts`).
- `/api/v1/*` in musicapi keeps a sunoapi.org-*compatible shape* so existing
  clients keep working. That is a response contract, **not** an upstream
  dependency — no request leaves for a reseller.

## The `base_url` columns

Migration `126_provider_base_url` still provides:

| Column | Meaning |
|---|---|
| `api_key_entries.base_url` | Host a key belongs to. `NULL` = host-agnostic. |
| `key_pool_configs.base_url` | Active upstream for the provider. `NULL` = use the env default. |

They now exist **only as an emergency escape hatch** — for example, pointing a
local install at `http://127.0.0.1:4003`. The admin Key Pool no longer offers a
reseller preset, so the UI cannot switch production back to a third party by
accident.

If a host is ever set that is not ours, treat it as an incident: check
`key_pool_configs.base_url`, clear it (Admin → Key Pool → Provider Settings →
Use default), and confirm `PLATFORM_SUNO_API_BASE_URL` points at our musicapi.

## History

- The reseller was used before musicapi reached parity (upload 3-step, MP4
  video, voice, MIDI, timestamped lyrics).
- musicapi now covers those paths itself, which is why the switch was removed.
