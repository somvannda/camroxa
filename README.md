# CAMXORA

White-label AI music-generation platform. The active product is **`camxora.com/`** — a
Next.js 16 web app backed by **`platform_api/`** (FastAPI), **`musicapi/`** (Fastify),
and **`admin_portal/`**, all credit-billed on top of a pool of Suno accounts.

## Active product

| Path | What it is | Dev port |
|---|---|---|
| `camxora.com/` | Customer web app — Next.js 16 | **3103** |
| `platform_api/` | Platform API — FastAPI | **8100** |
| `musicapi/` | Media/core API — Fastify 5, TypeScript | **4003** |
| `admin_portal/` | Operator console — React + Vite | **5173** |

Requirements: Node 20+, Python 3.11+, and PostgreSQL.

```bash
# web
cd camxora.com
npm install
npm run dev                    # :3103

# platform API
python -m uvicorn platform_api.main:app --host 127.0.0.1 --port 8100

# media/core API
cd musicapi
npm install
npm run serve                  # :4003

# admin
cd admin_portal
npm install
npm run dev                    # :5173
```

Full setup — env contracts, database migrations, the optional Redis job queue,
Google sign-in, and the script reference — lives in the individual READMEs.

## Canonical checkout

`G:\Developments\Projects\Camxora` is the canonical `main` checkout. Keep it on
`main`, clean, and up to date. Feature work belongs on short-lived branches and
worktrees; after merge, delete the branch, remove only clean merged worktrees,
and run `git worktree prune`.

## Legacy trees

The repository still contains the earlier Python/Electron incarnation. These are
kept for reference and are **not** part of the current product:

- `python_app/`, `camxora_python/` — legacy PyQt6 desktop app
- `music_web/` — legacy Next.js web app
- `camxora/`, `archive/electron-app/` — legacy Electron app

## Project rules

Contributor/agent rules live in [AGENTS.md](AGENTS.md). Commit, push, merge, and
production deploy happen only when the user explicitly asks.
