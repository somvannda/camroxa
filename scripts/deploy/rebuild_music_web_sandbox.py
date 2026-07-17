#!/usr/bin/env python3
"""Rebuild music_web on sandbox with correct API URL and restart service."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / ".venv" / "Lib" / "site-packages"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from deploy import build_source_tarball, ensure_deploy_key, load_secrets, ssh_connect  # noqa: E402


def main() -> int:
    secrets = load_secrets()
    client = ssh_connect(secrets["VPS_HOST"], secrets["VPS_USER"], ensure_deploy_key(), None)

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

cp /tmp/nginx-camxora-sandbox.conf /etc/nginx/sites-available/camxora-sandbox
nginx -t
systemctl reload nginx

sudo -u camxora bash -lc "
  set -e
  cd $REPO/music_web
  rm -rf .next
  npm ci || npm install --no-audit --no-fund
  cat > .env.production <<ENVEOF
NEXT_PUBLIC_API_BASE_URL=$API_URL
ENVEOF
  npm run build
"

mkdir -p /etc/systemd/system/camxora-music.service.d
cat > /etc/systemd/system/camxora-music.service.d/streaming-api.conf <<UNIT
[Service]
Environment=STREAMING_API_BASE_URL=http://127.0.0.1:8100
Environment=NEXT_PUBLIC_API_BASE_URL=$API_URL
UNIT

systemctl daemon-reload
systemctl restart camxora-music
sleep 3
systemctl is-active camxora-music

python3 - <<'PY'
import subprocess
html = subprocess.check_output(["curl", "-s", "http://127.0.0.1:3102/"], text=True)
print("contains track title:", "Sandbox Stream Test" in html)
print("shows empty state:", "No published tracks" in html)
PY
echo MUSIC_WEB_REBUILD_DONE
"""
    _, stdout, stderr = client.exec_command(cmd, get_pty=True)
    out = stdout.read().decode("utf-8", errors="replace")
    err = stderr.read().decode("utf-8", errors="replace")
    print(out)
    if err.strip():
        print(err)
    code = stdout.channel.recv_exit_status()
    client.close()
    return code


if __name__ == "__main__":
    raise SystemExit(main())
