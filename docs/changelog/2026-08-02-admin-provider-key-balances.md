# 2026-08-02 — Admin provider key balances on dashboard

## Summary

Admin Dashboard shows remaining credits/money **per key-pool label** so ops can top up on time.

- API: `GET /api/v1/admin/provider-key-balances` (optional `?refresh=true`)
- Providers: `suno`, `slai`, `fal`, `openai`, `deepseek`
- Live balance where the vendor exposes an API:
  - **Suno** — `/api/v1/generate/credit`
  - **DeepSeek** — `/user/balance`
  - **Fal** — `/v1/account/billing?expand=credits`
- **OpenAI** / often **SLAI**: no public balance API for normal secret keys → UI shows `N/A — check provider site` with guidance

Balances are cached ~45s in Redis. Dashboard panel refreshes on focus and via Refresh button.
