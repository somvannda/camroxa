# 2026-08-05 — SLAI remaining balance on Admin key balances

## Summary

Admin Dashboard **Key balances** now shows live SLAI remaining units per key-pool label.

- Uses official `GET https://slai-api.slai.shop/v1/balance` with Bearer auth
- Parses `balance.availableUnits` ÷ **1,000,000** → display credits (e.g. `271.69 credits`)
- OpenAI remains unsupported (no remaining-credit API)

## Surfaces

- `platform_api/services/provider_key_balance_service.py`
- Admin panel already renders `display` / `fetch_status` — no UI change required
