#!/usr/bin/env python3
"""Rebuild music_web on sandbox with correct API URL and restart service."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / ".venv" / "Lib" / "site-packages"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from deploy import (  # noqa: E402
    build_source_tarball,
    ensure_deploy_key,
    load_sandbox_secrets,
    resolve_sandbox_ssh,
    ssh_connect,
)


def main() -> int:
    secrets = load_sandbox_secrets()
    host, user, password = resolve_sandbox_ssh(secrets)
    print(f"Target sandbox host: {host}")
    client = ssh_connect(host, user, ensure_deploy_key(), password)

    archive = build_source_tarball()
    sftp = client.open_sftp()
    with sftp.file("/tmp/camxora-src.tar.gz", "wb") as remote_file:
        remote_file.write(archive.read_bytes())
    nginx_conf = Path(__file__).resolve().parent / "nginx-camxora-sandbox.conf"
    with sftp.file("/tmp/nginx-camxora-sandbox.conf", "wb") as remote_file:
        remote_file.write(nginx_conf.read_bytes())
    sftp.close()

    cmd = r"""
set -e
REPO=/opt/camxora/repo
API_URL=https://api.sandbox.camxora.com

tar -xzf /tmp/camxora-src.tar.gz -C $REPO music_web
chown -R camxora:camxora $REPO/music_web

# Update sandbox nginx site only; never enable if TLS certs are missing
# (avoids breaking production when this script is mis-targeted).
cp /tmp/nginx-camxora-sandbox.conf /etc/nginx/sites-available/camxora-sandbox
if [ -f /etc/letsencrypt/live/api.sandbox.camxora.com/fullchain.pem ]; then
  ln -sfn /etc/nginx/sites-available/camxora-sandbox /etc/nginx/sites-enabled/camxora-sandbox
  nginx -t && systemctl reload nginx
else
  echo "WARN: sandbox TLS certs missing; skipped nginx enable/reload"
fi

sudo -u camxora bash -lc "
  set -e
  cd $REPO/music_web
  rm -rf .next
  npm ci || npm install --no-audit --no-fund
  cat > .env.production <<ENVEOF
NEXT_PUBLIC_API_BASE_URL=$API_URL
NEXT_PUBLIC_USER_PORTAL_URL=https://app.sandbox.camxora.com
NEXT_PUBLIC_WEBSITE_URL=https://sandbox.camxora.com
NEXT_PUBLIC_CAMXORA_ENV=sandbox
ENVEOF
  npm run build
"

mkdir -p /etc/systemd/system/camxora-music.service.d
cat > /etc/systemd/system/camxora-music.service.d/streaming-api.conf <<UNIT
[Service]
Environment=STREAMING_API_BASE_URL=http://127.0.0.1:8100
Environment=NEXT_PUBLIC_API_BASE_URL=$API_URL
Environment=NEXT_PUBLIC_USER_PORTAL_URL=https://app.sandbox.camxora.com
Environment=NEXT_PUBLIC_WEBSITE_URL=https://sandbox.camxora.com
Environment=NEXT_PUBLIC_CAMXORA_ENV=sandbox
UNIT

systemctl daemon-reload
systemctl restart camxora-music
sleep 6
systemctl is-active camxora-music

python3 - <<'PY'
import subprocess, time
for _ in range(8):
    try:
        html = subprocess.check_output(["curl", "-sf", "http://127.0.0.1:3102/"], text=True)
        print("contains track title:", "Sandbox Stream Test" in html)
        print("shows empty state:", "No published tracks" in html)
        break
    except subprocess.CalledProcessError:
        time.sleep(1)
else:
    raise SystemExit("music_web not responding on :3102")
PY
echo MUSIC_WEB_REBUILD_DONE
"""
    _, stdout, stderr = client.exec_command(cmd, get_pty=True)
    out = stdout.read().decode("utf-8", errors="replace")
    err = stderr.read().decode("utf-8", errors="replace")
    # Windows consoles (cp1252) choke on npm spinner glyphs — print safely.
    try:
        print(out)
    except UnicodeEncodeError:
        print(out.encode("ascii", errors="replace").decode("ascii"))
    if err.strip():
        try:
            print(err)
        except UnicodeEncodeError:
            print(err.encode("ascii", errors="replace").decode("ascii"))
    code = stdout.channel.recv_exit_status()
    client.close()
    return code


if __name__ == "__main__":
    raise SystemExit(main())
