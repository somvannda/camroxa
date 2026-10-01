# musicapi

White-label AI music-generation platform: a REST API in the shape of `docs.sunoapi.org`,
backed by a pool of Suno accounts, plus a user workspace and an admin console.
Billing is credit-based.

## Layout

| Path | What it is | Dev port |
|---|---|---|
| `src/` | Core API — Fastify 5, TypeScript (ESM, run with `tsx`) | **4003** |
| `web-user/` | End-user workspace — Next.js 16 | **4001** |
| `web-admin/` | Operator console — Next.js 16 | **4002** |
| `migrations/` | Ordered, idempotent SQL migrations (`0001`–) | — |
| `scripts/` | Migration runner, probes, smoke tests, seed helpers | — |
| `docs/` | [State of the art & roadmap](docs/state-of-the-art-and-roadmap.md), [go-live plan](docs/production-readiness-plan.md) | — |

Requirements: Node 20+ and a reachable PostgreSQL. The local DB name is `sunoapi`.

## Local development

Three processes. Run each in its own terminal, **core first**.

### 1. Core API — port 4003

```bash
cd musicapi
npm install
cp .env.example .env          # then fill in the values below
npx tsx scripts/create-db.ts  # creates the `sunoapi` database if missing (safe to re-run)
npx tsx scripts/migrate.ts    # applies migrations/*.sql in order (safe to re-run)
npm run serve
```

`src/config.ts` **fails fast at boot** unless these are set:

| Variable | Requirement |
|---|---|
| `JWT_SECRET` | at least 32 characters, not the placeholder |
| `COOKIE_ENCRYPTION_KEY` | exactly 64 hex characters (32 bytes) |
| `DATABASE_URL` | e.g. `postgres://postgres:postgres@localhost:5432/sunoapi` |

`COOKIE_ENCRYPTION_KEY` decrypts `suno_accounts.client_cookie`. **It must stay stable** — changing it
makes every stored Suno cookie unreadable until each row is re-entered (see the rotation runbook in
`docs/production-readiness-plan.md` §1.8). A boot failure with
`Unsupported state or unable to authenticate data` means the key doesn't match the rows in the DB.

`SUNO_CLIENT_COOKIE` / `SUNO_DEVICE_ID` are only used as an `accounts.json` fallback when the
`suno_accounts` table is empty. See `.env.example` for the full list (OAuth, payment, rate-limit,
cookie/TLS, CORS and alert settings).

Verify: `GET http://localhost:4003/health` → `{"ok":true,...}`.

### 2. User workspace — port 4001

```bash
cd musicapi/web-user
npm install
npm run dev
```

### 3. Admin console — port 4002

```bash
cd musicapi/web-admin
npm install
npm run dev
```

Both frontends call the API through a relative `/backend/*` path that `next.config.ts` rewrites to
`BACKEND_URL` (falling back to `http://localhost:4003`), so cookies stay first-party and no extra
env is needed for local dev. `web-admin` additionally uses `BACKEND_URL` in `proxy.ts` to reject
non-admin sessions server-side.

### Google sign-in (optional)

Local Google OAuth needs the redirect URIs registered in Google Cloud Console:
`http://localhost:4001/auth/callback` and `http://localhost:4002/auth/callback`. Email/password
login works without this.

## Job queue (optional Redis)

Async jobs run in-process by default and are mirrored to the Postgres `jobs` table. Set
`QUEUE_DRIVER=redis` (with a reachable `REDIS_URL`) to move **descriptor-backed** jobs onto BullMQ
workers instead — the `jobs` table stays the system of record and only job ids travel through Redis.
That is what lets one process adopt work stranded by another's crash: on boot, `recoverJobs()`
re-queues those rows instead of failing them out.

```bash
docker run -d --name musicapi-redis -p 6379:6379 redis:7   # Redis >= 5.0 is required by BullMQ
QUEUE_DRIVER=redis REDIS_URL=redis://127.0.0.1:6379 npm run serve
```

Composite submissions (the music/sounds/lyrics builders) are not serializable yet and keep the
in-process path, so a mixed workload still needs a single node. `src/jobOps.ts` lists the ops that
are queue-eligible; `docs/state-of-the-art-and-roadmap.md` R4 explains the staging.

## Other scripts

```bash
npm run typecheck   # tsc --noEmit
npm run build       # tsc  -> dist/
npm start           # node dist/serve.js  (production entrypoint)
```

`scripts/` also holds the route probes and smoke tests used to verify the API surface — see
[ENDPOINT_STATUS.md](ENDPOINT_STATUS.md) for what each family has been checked against.

## More context

- [docs/state-of-the-art-and-roadmap.md](docs/state-of-the-art-and-roadmap.md) — architecture, gaps, remediation plan
- [docs/production-readiness-plan.md](docs/production-readiness-plan.md) — phased go-live plan
- [REQUIREMENTS.md](REQUIREMENTS.md) — product requirements
- [ENDPOINT_STATUS.md](ENDPOINT_STATUS.md) — endpoint verification matrix
