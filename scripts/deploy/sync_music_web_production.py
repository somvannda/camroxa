#!/usr/bin/env python3
"""Sync music_web source to production and rebuild."""

from __future__ import annotations

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from deploy import build_source_tarball, ensure_deploy_key, load_production_secrets, resolve_production_ssh, ssh_connect

# Remote output may contain non-ASCII; a Windows cp1252 console would otherwise
# raise UnicodeEncodeError after the remote work already succeeded.
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

PRODUCTION_HOST = "82.197.71.248"


def _run(client, cmd: str) -> int:
    _, stdout, stderr = client.exec_command(cmd, get_pty=True)
    while not stdout.channel.exit_status_ready():
        time.sleep(0.2)
    out = stdout.read().decode("utf-8", errors="replace")
    err = stderr.read().decode("utf-8", errors="replace")
    print(out)
    if err.strip():
        print(err)
    return stdout.channel.recv_exit_status()


def main() -> int:
    secrets = load_production_secrets()
    host, user, password = resolve_production_ssh(secrets)
    if host != PRODUCTION_HOST:
        raise SystemExit(f"Refusing non-production host: {host}")

    archive = build_source_tarball()
    client = ssh_connect(host, user, ensure_deploy_key(), password)
    sftp = client.open_sftp()
    with sftp.file("/tmp/camxora-src.tar.gz", "wb") as remote_file:
        remote_file.write(archive.read_bytes())
    sftp.close()

    code = _run(
        client,
        r"""
set -e
REPO=/opt/camxora/repo
API_URL=https://api.camxora.com
tar -xzf /tmp/camxora-src.tar.gz -C $REPO music_web
chown -R camxora:camxora $REPO/music_web
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
echo MUSIC_WEB_PRODUCTION_SYNC_DONE
""",
    )
    client.close()
    return code


if __name__ == "__main__":
    raise SystemExit(main())
