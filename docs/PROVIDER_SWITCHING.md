# Suno Provider Switching (sunoapi.org ↔ musicapi.camxora.com)

`platform_api` talks to a Suno-compatible reseller. It can point at
**sunoapi.org** (upstream `apibox.erweima.ai`) or Camxora's own
**`musicapi.camxora.com`** — the code accepts both response shapes — and the
active host can be switched **at runtime from the admin console**, with instant
rollback and no redeploy.

## How it works

Two nullable `base_url` columns (migration `126_provider_base_url`):

| Column | Meaning |
|---|---|
| `api_key_entries.base_url` | The upstream host a key belongs to. `NULL` = host-agnostic. |
| `key_pool_configs.base_url` | The **active** upstream for the provider. `NULL` = use the environment default and every active key (legacy). |

Selection rules:

- **No active host set** → every active key is eligible; the client uses
  `PLATFORM_SUNO_API_BASE_URL` (or the built-in default). This is the legacy
  behaviour and the default after the migration.
- **Active host set** → only keys whose `base_url` equals it are selected, and
  the client uses that host. So sunoapi.org and musicapi keys can coexist in one
  pool.

The active host is read from `key_pool_configs` on **every request**, so a change
takes effect immediately, across all workers.

## Switching (admin UI)

`Admin → Key Pool → <Suno provider> → Provider Settings`:

1. Add keys, tagging each with its host (**Add API Key → Upstream Host**):
   `https://musicapi.camxora.com` for musicapi, `https://apibox.erweima.ai`
   for sunoapi.org.
2. In **Provider Settings → Active Upstream Host**, pick a preset (or type the
   host), save. Generation now uses that host.
3. To roll back, pick the other host (or **Use default**).

The key list shows each key's host (or "Any host") so you can see which pool is
live.

## Switching (API)

```bash
# Tag a key with its host
curl -X POST "$API/api/v3/admin/key-pool/suno/keys" \
  -H "Authorization: Bearer $ADMIN_TOKEN" -H 'Content-Type: application/json' \
  -d '{"key_value":"mk_...","label":"musicapi-1","priority":10,
       "base_url":"https://musicapi.camxora.com"}'

# Activate musicapi  (base_url = host, or clear_base_url = true for the default)
curl -X PUT "$API/api/v3/admin/key-pool/suno/config" \
  -H "Authorization: Bearer $ADMIN_TOKEN" -H 'Content-Type: application/json' \
  -d '{"selection_strategy":"priority","cooldown_seconds":60,
       "base_url":"https://musicapi.camxora.com"}'

# Roll back
curl -X PUT "$API/api/v3/admin/key-pool/suno/config" \
  -H "Authorization: Bearer $ADMIN_TOKEN" -H 'Content-Type: application/json' \
  -d '{"selection_strategy":"priority","cooldown_seconds":60,"clear_base_url":true}'
```

## Notes

- **Environment default** stays `PLATFORM_SUNO_API_BASE_URL` (see
  `platform_api/config.py`). Setting an active host overrides it per request.
- **Deploy**: apply migration `126` (`alembic upgrade head`) before adding
  tagged keys.
- **Balance view** probes each key against its own host, so mixed pools report
  correctly.
- **Callbacks / record-info / WAV / lyrics** are account-scoped; with a
  multi-account pool the backend tries each key until the owning account answers
  (a 401/403 from a non-owner key is skipped, not treated as a failure).
- **Known gap**: musicapi does not return word-level lyric alignment, so
  timestamped lyrics / karaoke LRC come back empty on that host. Lyrics text is
  unaffected.
