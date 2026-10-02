# musicapi Production Deployment Plan

Doc id: `CAMXORA-MUSICAPI-PROD-DEPLOY-001`

A **musicapi-only** production deployment plan: the Suno core API (`musicapi/`) plus its
two Next.js fronts (`web-user`, `web-admin`), deployed to the production VPS by the
dedicated driver. It deliberately excludes the platform-wide cutover items (website,
`platform_api`, `user_portal`, desktop installer, CutLuy KHQR billing) — those live in
`docs/PRODUCTION_CUTOVER.md` and are out of scope here.

## 1. Scope

**In scope**

- `musicapi/` — Fastify 5 + TypeScript core API (port `4003`).
- `musicapi/web-user` — Next.js user panel (port `4001`).
- `musicapi/web-admin` — Next.js admin panel (port `4002`).
- The deploy plumbing that ships only those trees plus `scripts/deploy/`:
  `scripts/deploy/deploy_musicapi_production.py` → `sync_musicapi_sandbox.py` →
  `scripts/deploy/camxora-musicapi-remote.sh`.

**Out of scope (do not do as part of this deploy)**

- Desktop v1.0.0 build/release.
- `platform_api` billing — CutLuy KHQR (`PLATFORM_CUTLUY_*`). musicapi checkout is
  **ChmabaPay** (`CHMABA_*`), a separate gateway.
- Platform config migration, plans import, streaming/B2 catalog copy.
- `web-user`/`platform` shared database (the platform's `camxora` DB). musicapi uses its
  own DB `sunoapi`.

The driver only packages `musicapi` + `scripts/deploy` (see `PACKAGE_DIRS` in
[sync_musicapi_sandbox.py](file:///g:/Developments/Projects/Camxora/MusicGenerator-musicapi-integration/scripts/deploy/sync_musicapi_sandbox.py#L58)), so this chain cannot
touch platform code by construction.

## 2. Target topology

| | Value |
|---|---|
| Production VPS | `82.197.71.248` (`VPS_HOST` in `.deploy/secrets.production.env`) |
| SSH user | `root` (`VPS_USER`) |
| Apex (`musicapi.camxora.com`) | User portal + landing page → `127.0.0.1:4001`; **API mounted by path** (`/backend`, `/v1`, `/api/v1`, `/health`, `/payments`, `/me/download`) → `127.0.0.1:4003` |
| Admin panel | `admin.musicapi.camxora.com` → `127.0.0.1:4002` |
| App root on host | `/opt/camxora/repo/musicapi` |
| Generated secrets | `/opt/camxora/.deploy-secrets` (mode `600`) |
| TLS cert | `/etc/letsencrypt/live/musicapi.camxora.com/` |
| DB | Postgres `sunoapi`, role `musicapi` |

The production domain derives from `MUSICAPI_ENV=production` →
`MUSICAPI_DOMAIN=camxora.com` in
[camxora-musicapi-remote.sh](file:///g:/Developments/Projects/Camxora/MusicGenerator-musicapi-integration/scripts/deploy/camxora-musicapi-remote.sh#L48-L55).

## 3. Prerequisites

### 3.1 DNS

Two A records must point at `82.197.71.248` **before** the first `--issue-cert` run,
otherwise Let's Encrypt HTTP-01 validation fails and the remote installer skips the HTTPS
vhost:

- `musicapi.camxora.com` (apex — landing, user portal, and API by path)
- `admin.musicapi.camxora.com`

There is no `app.musicapi.camxora.com` host: the portals route all API traffic through the
relative `/backend/*` path, so the apex only needs the API prefixes proxied to the core.

### 3.2 Secrets file

Create `.deploy/secrets.production.env` from
[.deploy/secrets.production.env.example](file:///g:/Developments/Projects/Camxora/MusicGenerator-musicapi-integration/.deploy/secrets.production.env.example).
Production **has no legacy fallback** — if the file is absent, the driver exits `1`
before connecting. Never commit this file.

Required keys:

| Key | Purpose |
|---|---|
| `VPS_HOST` | `82.197.71.248` |
| `VPS_USER` | `root` |
| `VPS_PASSWORD` or `VPS_SSH_KEY` | SSH auth (key preferred; falls back to the repo deploy key) |
| `CERTBOT_EMAIL` | Let's Encrypt registration / expiry mail |

musicapi deploy keys (forwarded automatically — anything truthy with a `MUSICAPI_`
prefix; leave blank to have the host generate + persist it):

| Key | Notes |
|---|---|
| `MUSICAPI_DB_PASSWORD` | Generated on host if blank (24-byte hex), persisted |
| `MUSICAPI_JWT_SECRET` | Generated on host if blank (48-byte hex), persisted |
| `MUSICAPI_COOKIE_ENCRYPTION_KEY` | Generated on host if blank (32-byte hex), persisted; **change requires re-encrypting stored Suno cookies** |
| `MUSICAPI_SUNO_CLIENT_COOKIE`, `MUSICAPI_SUNO_DEVICE_ID`, `MUSICAPI_SUNO_JWT`, `MUSICAPI_SUNO_CAPTCHA_TOKEN` | Suno account credentials |
| `MUSICAPI_TWOCAPTCHA_KEY` | 2Captcha |
| `MUSICAPI_GOOGLE_CLIENT_ID`, `MUSICAPI_GOOGLE_CLIENT_SECRET` | Google OAuth for the **user app only** (`GOOGLE_REDIRECT_URI_USER` is derived from the apex host). Admin uses email/password — its redirect URI is intentionally not allowlisted. |
| `MUSICAPI_CHMABA_API_KEY`, `MUSICAPI_CHMABA_STORE_ID`, `MUSICAPI_CHMABA_WEBHOOK_SECRET` | ChmabaPay live checkout. **Blank ⇒ `.env` gets empty `CHMABA_*` and checkout returns 503.** |
| `MUSICAPI_FRONTEND_ORIGINS` | Defaults to `https://musicapi.camxora.com,https://admin.musicapi.camxora.com` |
| `MUSICAPI_LOG_LEVEL` | Defaults to `info` |
| `MUSICAPI_ALERT_TELEGRAM_BOT_TOKEN`, `MUSICAPI_ALERT_TELEGRAM_CHAT_ID` | Health-alert bot; falls back to `TELEGRAM_BOT_TOKEN` / `PLATFORM_TELEGRAM_*` if present |
| `MUSICAPI_BACKUP_DIR` | Defaults to `/opt/camxora/backups/musicapi` |
| `MUSICAPI_BACKUP_RETENTION_DAYS` | Defaults to `14` |

> The production example ships the `MUSICAPI_*` block commented out — uncomment and fill
> the keys you have; leave the rest blank.

### 3.3 Operator machine

- Python 3 with `paramiko` (the driver runs `ensure_paramiko()`).
- Network access to `82.197.71.248:22`.
- Repo checked out on `main`; the deploy tars the **working tree**, so commit/stash first.

## 4. Deploy

```bash
python scripts/deploy/deploy_musicapi_production.py --yes
```

First deploy (DNS ready, no cert yet):

```bash
python scripts/deploy/deploy_musicapi_production.py --yes --issue-cert
```

- `--yes` is a hard gate — without it the driver prints a refusal and returns `2`.
- `--issue-cert` bootstraps Let's Encrypt on the first run only; drop it afterwards
  (certbot renews on its own). Re-run with it if the cert is missing and DNS has since
  been fixed.
- Success is reported only when the remote output contains the sentinel
  `MUSICAPI_PRODUCTION_DEPLOYED`.

## 5. What the deploy does

1. **Package** — tar `musicapi/` + `scripts/deploy/` and upload to
   `/tmp/musicapi-src.tar.gz`; upload `camxora-musicapi-remote.sh` (CRLF→LF, `chmod 755`).
2. **Run remote installer as root** with `MUSICAPI_ENV=production`, `SYNC_FROM_LOCAL=1`,
   `ISSUE_CERT`, `CERTBOT_EMAIL`, and every `MUSICAPI_*` secret exported.
3. **Resolve/generate secrets** — host value → persisted `/opt/camxora/.deploy-secrets` →
   fresh `openssl rand`. Persisted so JWT sessions and encrypted Suno cookies survive
   redeploys.
4. **System packages** — nginx, certbot, Postgres, git/curl/build-essential, Node.js 20.
5. **User + DB** — `camxora` system user; Postgres role `musicapi` + DB `sunoapi`
   (create-or-alter password, grants).
6. **Extract source** — replace `/opt/camxora/repo/musicapi` wholesale.
7. **Write `musicapi/.env` (mode 600) — wholesale rewrite.** This is the critical
   invariant: `NODE_ENV`, `PORT=4003`, `BACKEND_URL`, `DATABASE_URL`, `JWT_SECRET`,
   `COOKIE_ENCRYPTION_KEY`, `TRUST_PROXY=127.0.0.1`, `FRONTEND_ORIGINS`, `LOG_LEVEL`, the
   `SUNO_*` / `TWOCAPTCHA_KEY` / `GOOGLE_*` / `BAKONG_*` / `CHMABA_*` blocks, and
   `ALERT_TELEGRAM_*` / `BACKUP_*`. **Never hand-edit `.env` on the host** — the next
   deploy overwrites it. Add secrets to the secrets file instead.
8. **Build core** — `npm ci || npm install`, `npm run build` (`tsc` → `dist/`).
9. **Migrations** — `tsx scripts/migrate.ts`.
10. **Build frontends** — for `web-user` and `web-admin`: `npm ci || npm install`, write
    `.env.production` with `BACKEND_URL=http://127.0.0.1:4003`, `npm run build`.
11. **systemd** — `install_musicapi_services.sh` installs/enables
    `camxora-musicapi`, `camxora-musicapi-web-user`, `camxora-musicapi-web-admin`, plus the
    `camxora-musicapi-backup` and `camxora-musicapi-healthcheck` service/timer pairs.
12. **First backup + health probe** — starts the backup and healthcheck units once; the
    timers take over.
13. **nginx** — copies `nginx-musicapi-production.conf` to
    `sites-available/musicapi-production` and links it. If the cert is missing and
    `ISSUE_CERT=1`, stands up a temporary :80 site and runs
    `certbot --nginx -d <apex> -d <admin> --expand --non-interactive --agree-tos --redirect`.
    If still no cert, the HTTPS vhost is **skipped with a WARN**.

## 6. Verification

On the host (the remote installer prints most of these):

```bash
curl -sf https://musicapi.camxora.com/health          # {"ok":true,...}
curl -s  -o /dev/null -w '%{http_code}\n' https://musicapi.camxora.com/           # user portal (200)
curl -s  -o /dev/null -w '%{http_code}\n' https://musicapi.camxora.com/v1/models  # public API
curl -s  -o /dev/null -w '%{http_code}\n' https://admin.musicapi.camxora.com/     # admin (200)
curl -s  -o /dev/null -w '%{http_code}\n' https://musicapi.camxora.com/metrics   # 401 anon
systemctl is-active camxora-musicapi camxora-musicapi-web-user camxora-musicapi-web-admin nginx postgresql
systemctl list-timers camxora-musicapi-backup.timer camxora-musicapi-healthcheck.timer
```

- `/health` returns `{"ok":true,...}`; an empty account pool is expected until a Suno
  account is seeded.
- `/metrics` must be `401` for anonymous callers (admin-guarded).
- All three units `active` and the two timers scheduled.
- A fresh backup file exists under `MUSICAPI_BACKUP_DIR`.

## 7. Redeploy / rollback

- **Redeploy** is the same command (`--yes`, no `--issue-cert`). It is idempotent and
  reuses persisted secrets, so sessions and encrypted cookies stay valid.
- **Rollback** is a redeploy of the previous commit: `git checkout <sha>` →
  `deploy_musicapi_production.py --yes`. Migrations are forward-only — verify before
  rolling back a release that added one.
- **Full restart without a rebuild:** `systemctl restart camxora-musicapi`.

## 8. Notes

- Long jobs (Suno generation, downloads) are why core locations use 600 s proxy timeouts;
  nginx is the only edge (`TRUST_PROXY=127.0.0.1`), no Cloudflare headers.
- The `--yes` gate enforces the Phase-4 rule: production deploys happen only on an
  explicit ask.
- Deploy-script history and rationale (CRLF root cause, systemd choice, nginx decisions)
  are in `musicapi/docs/production-readiness-plan.md` Phase 4.
