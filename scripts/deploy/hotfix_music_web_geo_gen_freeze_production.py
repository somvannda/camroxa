#!/usr/bin/env python3
"""File-scoped production hotfix: music-web KH geo + generation freeze + play login fix.

Uploads allowlisted files only. Does not sync a full platform_api or admin tree.
Does not run alembic upgrade heads.
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PRIMARY = Path(r"D:\Development\Projects\Electron\MusicGenerator")
SCRIPT_DIR = Path(__file__).resolve().parent
_DEPLOY_CANDIDATES = [PRIMARY / "scripts" / "deploy", SCRIPT_DIR]
for candidate in _DEPLOY_CANDIDATES:
    venv_site = candidate / ".venv" / "Lib" / "site-packages"
    if venv_site.is_dir():
        sys.path.insert(0, str(venv_site))
    if (candidate / "deploy.py").is_file():
        sys.path.insert(0, str(candidate))
        break

from deploy import (  # noqa: E402
    ensure_deploy_key,
    load_production_secrets,
    resolve_production_ssh,
    ssh_connect,
)

PRODUCTION_HOST = "82.197.71.248"
FILES = [
    "platform_api/middleware/geo_access.py",
    "platform_api/services/generation_freeze.py",
    "platform_api/middleware/abuse_detection.py",
    "platform_api/middleware/auth.py",
    "platform_api/middleware/rate_limit.py",
    "platform_api/routers/auth.py",
    "platform_api/routers/users.py",
    "platform_api/routers/web_music.py",
    "platform_api/services/abuse_alert_service.py",
    "platform_api/services/audio_origin_proxy.py",
    "platform_api/config.py",
    "platform_api/exceptions.py",
    "platform_api/main.py",
    "admin_portal/src/hooks/use-users.ts",
    "admin_portal/src/pages/users/user-detail.tsx",
    "admin_portal/src/types/models.ts",
    "music_web/src/components/create-page-client.tsx",
    "music_web/src/components/player-provider.tsx",
    "music_web/src/lib/auth-api.ts",
    "music_web/src/lib/streaming-api.ts",
    "music_web/src/lib/web-music-api.ts",
]


def _run(client, cmd: str, timeout: int = 900) -> tuple[int, str]:
    _, stdout, stderr = client.exec_command(cmd, get_pty=True, timeout=timeout)
    while not stdout.channel.exit_status_ready():
        time.sleep(0.2)
    out = stdout.read().decode("utf-8", errors="replace")
    err = stderr.read().decode("utf-8", errors="replace")
    code = stdout.channel.recv_exit_status()
    return code, out + ("\n" + err if err.strip() else "")


def main() -> int:
    secrets = load_production_secrets()
    host, user, password = resolve_production_ssh(secrets)
    if host != PRODUCTION_HOST:
        raise SystemExit(f"Refusing non-production host: {host}")
    print(f"Target production host: {host}", flush=True)

    missing = [rel for rel in FILES if not (ROOT / rel).is_file()]
    if missing:
        raise SystemExit(f"Missing source files: {missing}")

    nginx_conf = SCRIPT_DIR / "nginx-camxora-production.conf"
    if not nginx_conf.is_file():
        raise SystemExit(f"Missing nginx config: {nginx_conf}")

    client = ssh_connect(host, user, ensure_deploy_key(), password)
    try:
        sftp = client.open_sftp()
        for rel in FILES:
            remote = f"/opt/camxora/repo/{rel.replace(chr(92), '/')}"
            parent = "/".join(remote.split("/")[:-1])
            client.exec_command(f"mkdir -p {parent}")
            print(f"Uploading {rel} ...", flush=True)
            sftp.put(str(ROOT / rel), remote)
        print("Uploading nginx-camxora-production.conf ...", flush=True)
        sftp.put(str(nginx_conf), "/tmp/nginx-camxora-production.conf")
        sftp.close()

        code, out = _run(
            client,
            r"""
set -e
REPO=/opt/camxora/repo
chown camxora:camxora \
  $REPO/platform_api/middleware/geo_access.py \
  $REPO/platform_api/services/generation_freeze.py \
  $REPO/platform_api/middleware/abuse_detection.py \
  $REPO/platform_api/middleware/auth.py \
  $REPO/platform_api/middleware/rate_limit.py \
  $REPO/platform_api/routers/auth.py \
  $REPO/platform_api/routers/users.py \
  $REPO/platform_api/routers/web_music.py \
  $REPO/platform_api/services/abuse_alert_service.py \
  $REPO/platform_api/services/audio_origin_proxy.py \
  $REPO/platform_api/config.py \
  $REPO/platform_api/exceptions.py \
  $REPO/platform_api/main.py \
  $REPO/admin_portal/src/hooks/use-users.ts \
  $REPO/admin_portal/src/pages/users/user-detail.tsx \
  $REPO/admin_portal/src/types/models.ts \
  $REPO/music_web/src/components/create-page-client.tsx \
  $REPO/music_web/src/components/player-provider.tsx \
  $REPO/music_web/src/lib/auth-api.ts \
  $REPO/music_web/src/lib/streaming-api.ts \
  $REPO/music_web/src/lib/web-music-api.ts

echo '=== import check ==='
cd /opt/camxora/repo
PYTHONPATH=/opt/camxora/repo /opt/camxora/repo/platform_api/.venv/bin/python -c \
  "from platform_api.middleware.geo_access import MusicWebGeoMiddleware; from platform_api.services.generation_freeze import freeze_generation; print('IMPORT_OK')"

echo '=== nginx ==='
cp /tmp/nginx-camxora-production.conf /etc/nginx/sites-available/camxora-production
ln -sf /etc/nginx/sites-available/camxora-production /etc/nginx/sites-enabled/camxora-production
nginx -t
systemctl reload nginx

echo '=== restart api ==='
systemctl restart camxora-api
code=""
for i in 1 2 3 4 5 6 7 8 9 10 11 12 13 14 15 16 17 18 20; do
  code=$(curl -sS -m 3 -o /tmp/prod_health.json -w '%{http_code}' http://127.0.0.1:8100/health || true)
  echo attempt_$i health=$code
  if [ "$code" = "200" ]; then
    break
  fi
  sleep 2
done
echo HEALTH_BODY
cat /tmp/prod_health.json || true
echo
test "$code" = "200"

echo '=== rebuild music_web ==='
API_URL=https://api.camxora.com
sudo -u camxora bash -lc "
  set -e
  cd $REPO/music_web
  rm -rf .next
  npm ci || npm install --no-audit --no-fund
  TURNSTILE_SITE=\$(grep -m1 '^CLOUDFLARE_TURNSTILE_SITE_KEY=' $REPO/platform_api/.env | cut -d= -f2- || true)
  cat > .env.production <<ENVEOF
NEXT_PUBLIC_API_BASE_URL=$API_URL
NEXT_PUBLIC_USER_PORTAL_URL=https://app.camxora.com
NEXT_PUBLIC_WEBSITE_URL=https://camxora.com
NEXT_PUBLIC_CAMXORA_ENV=production
NEXT_PUBLIC_CLOUDFLARE_TURNSTILE_SITE_KEY=\$TURNSTILE_SITE
ENVEOF
  npm run build
"
systemctl restart camxora-music
sleep 4
systemctl is-active camxora-music

echo '=== rebuild admin_portal ==='
sudo -u camxora bash -lc "
  set -e
  cd $REPO/admin_portal
  npm ci || npm install --no-audit --no-fund
  npm run build
"
echo GEO_GEN_FREEZE_PROD_DONE
""",
            timeout=900,
        )
        try:
            print(out)
        except UnicodeEncodeError:
            print(out.encode("ascii", errors="replace").decode("ascii"))
        print(f"exit={code}", flush=True)
        if code != 0 or "GEO_GEN_FREEZE_PROD_DONE" not in out:
            raise SystemExit("Production geo/freeze hotfix did not finish cleanly.")
        return 0
    finally:
        client.close()


if __name__ == "__main__":
    raise SystemExit(main())
