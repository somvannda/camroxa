# admin_portal

React + Vite admin console for Camxora. Runs on port **5173**.

## Run locally

```bash
npm install
npx vite --port 5173 --strictPort
```

## The API proxy (read this first)

Vite proxies `/api` to `VITE_API_PROXY_TARGET`, which defaults to
`http://127.0.0.1:8000`:

```ts
// vite.config.ts
proxy: {
  '/api': { target: env.VITE_API_PROXY_TARGET?.trim() || 'http://127.0.0.1:8000' },
}
```

If the platform API is not on 8000 — for example the Creator Program preview,
which runs on **8101** — you must pass the target, or every request returns 401
and the app bounces you to `/login` even with a valid session:

```bash
# PowerShell
$env:VITE_API_PROXY_TARGET="http://127.0.0.1:8101"; npx vite --port 5173 --strictPort
```

```bash
# bash
VITE_API_PROXY_TARGET=http://127.0.0.1:8101 npx vite --port 5173 --strictPort
```

A 401 on `/api/v3/users/me` while the API is healthy almost always means the
proxy is pointing at the wrong port.

## Auth

- Tokens are stored in **`sessionStorage`** under `camxora_admin_access_token`
  and `camxora_admin_refresh_token` — not `localStorage`. A token placed in
  `localStorage` is ignored.
- On boot the console calls `GET /api/v3/users/me` and requires
  `role === 'admin'`; anything else is logged out.
- Requests carry `X-Portal-Context: admin` plus the bearer token.

## Creator Program screens

| Route | Purpose |
|---|---|
| `/creators/kyc` | Payout identity review; documents open through a 5-minute signed URL |
| `/creators/applications` | Optional badge requests |
| `/creators/releases` | Release moderation and takedown |
| `/creators/payouts` | Payout queue, maker-checker, bank CSV, KHR rate |
| `/creators/royalties` | Period calculation, lock, reserve release, tax statements, reconciliation |

Payouts settle in **KHR or USD**. The KHR rate must be between 3,500 and 5,000
riel per USD; anything outside that range is rejected as a typo.

## Typecheck

```bash
npx tsc --noEmit -p tsconfig.json
```
