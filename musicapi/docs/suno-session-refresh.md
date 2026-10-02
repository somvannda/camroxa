# Suno session auto-refresh

> Problem: a Suno **access JWT** lasts ~1 hour and cannot be refreshed. Pasting a
> new one by hand every hour does not scale.
> Solution: store the durable Clerk **`__client` cookie** per account; the API
> mints fresh JWTs from it automatically, persists Clerk's cookie rotations, and
> keeps sessions warm in the background.

## Two kinds of credential

| Stored value | Lifetime | Refreshable? |
|---|---|---|
| `__client` cookie (Clerk refresh cookie) | months | **Yes** — mint JWT via Clerk |
| Access JWT (`eyJ…`) | ~1 hour | **No** — used as-is until it expires |

`SunoClient.resolveJwt()` detects which one it has: a `__client` cookie goes
through Clerk (`/v1/client` → session → `/tokens`); a raw JWT is passed straight
through. **For unattended operation, always seed the `__client` cookie.**

## What refreshes automatically

1. **JWT mint/renew (per account)** — `SunoClient.resolveJwt()` mints a JWT from
   the stored `__client` cookie and caches it. It renews **proactively ~5 min
   before expiry** (decoded from the JWT `exp`), and also on any `401/403`
   (`refreshJwt()`), so in-flight jobs don't fail mid-song.
2. **Cookie rotation persistence** — Clerk can rotate `__client` via `Set-Cookie`.
   `SunoClient.captureSetCookie()` reads it, updates the in-memory account, and
   calls `AccountCreds.persistCookie`, which the pool wires to re-encrypt and
   `UPDATE suno_accounts SET client_cookie = …` (AES-256-GCM, `enc:v1:`).
   Missing this rotation is what eventually kills a session.
3. **Keep-alive loop** — `AccountPool.refreshSessions()` is called on an interval
   (default **30 min**, `SUNO_KEEPALIVE_MS`; `0` disables) so long idle periods
   never let the session lapse.

## Seeding a durable account

Use `scripts/add-paid-account.ts` and pass the **`__client` cookie value** (not a
JWT) as `PAID_JWT`:

```bash
PAID_JWT='<__client cookie value>' \
PAID_LABEL='iamduke1987@gmail.com' \
PAID_DEVICE_ID='<optional device id>' \
npx tsx scripts/add-paid-account.ts
```

Get the `__client` value from a signed-in `suno.com` tab:
DevTools → Application → Cookies → `https://suno.com` → `__client`.

> If the row currently holds a bare JWT (from the earlier reseed), replace it with
> the `__client` cookie — otherwise auto-refresh has nothing to refresh.

## Config

| Env | Default | Meaning |
|---|---|---|
| `SUNO_KEEPALIVE_MS` | `1800000` (30 min) | Session keep-alive interval; `0` disables |

No other env is needed; the mechanism is per-account and DB-backed.

## Verifying

- On boot: log line `suno session keep-alive started`.
- After a generation, `suno_accounts.client_cookie` may change (rotation) — that's
  expected and safe (re-encrypted).
- If an account keeps failing with `no active Clerk session`, the `__client`
  cookie is expired/revoked → re-seed it (step above).
