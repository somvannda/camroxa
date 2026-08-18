#!/usr/bin/env python3
"""File-scoped sandbox hotfix: catalog cache, Create pre-upload, bounded ranges."""

from __future__ import annotations

import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DEPLOY = ROOT / "scripts" / "deploy"
sys.path.insert(0, str(DEPLOY / "venv" / "Lib" / "site-packages"))
sys.path.insert(0, str(DEPLOY / ".venv" / "Lib" / "site-packages"))
sys.path.insert(0, str(DEPLOY))

from deploy import ensure_deploy_key, load_sandbox_secrets, resolve_sandbox_ssh, ssh_connect  # noqa: E402

SANDBOX_HOST = "46.250.235.83"
FILES = [
    "platform_api/services/audio_origin_proxy.py",
    "platform_api/services/web_music_service.py",
    "platform_api/services/streaming_catalog_service.py",
    "platform_api/services/streaming_upload_service.py",
    "platform_api/routers/callbacks.py",
    "platform_api/routers/streaming_public.py",
    "platform_api/routers/web_music.py",
    "music_web/src/components/player-provider.tsx",
]


def main() -> int:
    secrets = load_sandbox_secrets()
    host, user, password = resolve_sandbox_ssh(secrets)
    if host != SANDBOX_HOST:
        raise SystemExit(f"Refusing non-sandbox host: {host}")
    print(f"Target sandbox host: {host}", flush=True)
    nginx_conf = DEPLOY / "nginx-camxora-sandbox.conf"
    if not nginx_conf.is_file():
        raise SystemExit(f"Missing nginx config: {nginx_conf}")
    client = ssh_connect(host, user, ensure_deploy_key(), password)
    try:
        sftp = client.open_sftp()
        for rel in FILES:
            remote = f"/opt/camxora/repo/{rel}"
            print(f"Uploading {rel} ...", flush=True)
            sftp.put(str(ROOT / rel), remote)
        print("Uploading nginx-camxora-sandbox.conf ...", flush=True)
        sftp.put(str(nginx_conf), "/tmp/nginx-camxora-sandbox.conf")
        sftp.close()
        cmd = r"""
set -e
REPO=/opt/camxora/repo
chown camxora:camxora \
  $REPO/platform_api/services/audio_origin_proxy.py \
  $REPO/platform_api/services/web_music_service.py \
  $REPO/platform_api/services/streaming_catalog_service.py \
  $REPO/platform_api/services/streaming_upload_service.py \
  $REPO/platform_api/routers/callbacks.py \
  $REPO/platform_api/routers/streaming_public.py \
  $REPO/platform_api/routers/web_music.py \
  $REPO/music_web/src/components/player-provider.tsx

echo '=== nginx cache dir ==='
mkdir -p /var/cache/nginx/camxora_catalog_audio
chown www-data:www-data /var/cache/nginx/camxora_catalog_audio || chown nginx:nginx /var/cache/nginx/camxora_catalog_audio || true
cp /tmp/nginx-camxora-sandbox.conf /etc/nginx/sites-available/camxora-sandbox
ln -sf /etc/nginx/sites-available/camxora-sandbox /etc/nginx/sites-enabled/camxora-sandbox
nginx -t
systemctl reload nginx

echo '=== restart api ==='
systemctl restart camxora-api
code=""
for i in 1 2 3 4 5 6 7 8 9 10 11 12 13 14 15 16 17 18 20; do
  code=$(curl -sS -m 3 -o /tmp/sandbox_health.json -w '%{http_code}' http://127.0.0.1:8100/health || true)
  echo attempt_$i health=$code
  if [ "$code" = "200" ]; then
    break
  fi
  sleep 2
done
test "$code" = "200"

echo '=== rebuild music_web ==='
API_URL=https://api.sandbox.camxora.com
sudo -u camxora bash -lc "
  set -e
  cd $REPO/music_web
  rm -rf .next
  npm ci || npm install --no-audit --no-fund
  TURNSTILE_SITE=\$(grep -m1 '^CLOUDFLARE_TURNSTILE_SITE_KEY=' $REPO/platform_api/.env | cut -d= -f2- || true)
  cat > .env.production <<ENVEOF
NEXT_PUBLIC_API_BASE_URL=$API_URL
NEXT_PUBLIC_USER_PORTAL_URL=https://app.sandbox.camxora.com
NEXT_PUBLIC_WEBSITE_URL=https://sandbox.camxora.com
NEXT_PUBLIC_CAMXORA_ENV=sandbox
NEXT_PUBLIC_CLOUDFLARE_TURNSTILE_SITE_KEY=\$TURNSTILE_SITE
ENVEOF
  npm run build
"
systemctl restart camxora-music
sleep 4
systemctl is-active camxora-music
echo CATALOG_CACHE_SANDBOX_DONE
"""
        _, stdout, stderr = client.exec_command(cmd, get_pty=True, timeout=480)
        while not stdout.channel.exit_status_ready():
            time.sleep(0.2)
        out = stdout.read().decode("utf-8", errors="replace")
        code = stdout.channel.recv_exit_status()
        print(out.encode("ascii", errors="replace").decode("ascii"))
        print(f"exit={code}", flush=True)
        return code
    finally:
        client.close()


if __name__ == "__main__":
    raise SystemExit(main())
