# CAMXORA

White-label AI music-generation platform. The active product is **`musicapi/`** — a
Fastify + TypeScript core API, a Next.js user workspace, and a Next.js admin console,
all credit-billed on top of a pool of Suno accounts.

## Active product — `musicapi/`

| Path | What it is | Dev port |
|---|---|---|
| `musicapi/src/` | Core API — Fastify 5, TypeScript (ESM, run with `tsx`) | **4003** |
| `musicapi/web-user/` | End-user workspace — Next.js 16 | **4001** |
| `musicapi/web-admin/` | Operator console — Next.js 16 | **4002** |

Requirements: Node 20+ and a reachable PostgreSQL (local DB name `sunoapi`).

```bash
cd musicapi
npm install
cp .env.example .env          # fill in JWT_SECRET, COOKIE_ENCRYPTION_KEY, DATABASE_URL
npx tsx scripts/create-db.ts  # creates the `sunoapi` database if missing
npx tsx scripts/migrate.ts    # applies migrations/*.sql in order
npm run serve                 # core API on :4003
```

Then, each in its own terminal:

```bash
cd musicapi/web-user  && npm install && npm run dev   # :4001
cd musicapi/web-admin && npm install && npm run dev   # :4002
```

Full setup — env contract, the optional Redis job queue, Google sign-in, and the
script reference — lives in [musicapi/README.md](musicapi/README.md).

## Legacy trees

The repository still contains the earlier Python/Electron incarnation. These are
kept for reference and are **not** part of the current product:

- `platform_api/` — legacy FastAPI backend
- `python_app/`, `camxora_python/` — legacy PyQt6 desktop app
- `admin_portal/` — legacy React + Vite admin portal
- `music_web/` — legacy Next.js web app
- `camxora/`, `archive/electron-app/` — legacy Electron app

## Project rules

Contributor/agent rules live in [AGENTS.md](AGENTS.md). Commit, push, merge, and
production deploy happen only when the user explicitly asks.
