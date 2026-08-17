#!/usr/bin/env python3
"""File-scoped sandbox hotfix: Create clips play distinct audio."""

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
    "music_web/src/components/player-provider.tsx",
    "music_web/src/components/create-page-client.tsx",
]


def main() -> int:
    secrets = load_sandbox_secrets()
    host, user, password = resolve_sandbox_ssh(secrets)
    if host != SANDBOX_HOST:
        raise SystemExit(f"Refusing non-sandbox host: {host}")
    print(f"Target sandbox host: {host}", flush=True)
    client = ssh_connect(host, user, ensure_deploy_key(), password)
    try:
        sftp = client.open_sftp()
        for rel in FILES:
            remote = f"/opt/camxora/repo/{rel}"
            print(f"Uploading {rel} ...", flush=True)
            sftp.put(str(ROOT / rel), remote)
        sftp.close()
        cmd = r"""
set -e
REPO=/opt/camxora/repo
chown camxora:camxora \
  $REPO/platform_api/services/audio_origin_proxy.py \
  $REPO/platform_api/services/web_music_service.py \
  $REPO/music_web/src/components/player-provider.tsx \
  $REPO/music_web/src/components/create-page-client.tsx
systemctl restart camxora-api
sleep 3
systemctl is-active camxora-api
curl -sS -m 8 -o /dev/null -w 'health=%{http_code}\n' http://127.0.0.1:8100/health
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
echo DISTINCT_CLIP_SANDBOX_DONE
"""
        _, stdout, stderr = client.exec_command(cmd, get_pty=True, timeout=420)
        while not stdout.channel.exit_status_ready():
            time.sleep(0.2)
        out = stdout.read().decode("utf-8", errors="replace")
        print(out.encode("ascii", errors="replace").decode("ascii"))
        return stdout.channel.recv_exit_status()
    finally:
        client.close()


if __name__ == "__main__":
    raise SystemExit(main())
