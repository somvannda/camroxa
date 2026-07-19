#!/usr/bin/env python3
"""Deploy platform_api (billing 064 + Suno/image fixes), migrate, configure Suno IPs."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / ".venv" / "Lib" / "site-packages"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from deploy import build_source_tarball, ensure_deploy_key, load_secrets, ssh_connect  # noqa: E402

SUNO_CALLBACK_IPS = "47.89.217.55,47.77.231.163,47.251.163.235"


def main() -> int:
    secrets = load_secrets()
    client = ssh_connect(secrets["VPS_HOST"], secrets["VPS_USER"], ensure_deploy_key(), None)

    archive = build_source_tarball()
    sftp = client.open_sftp()
    with sftp.file("/tmp/camxora-src.tar.gz", "wb") as remote_file:
        remote_file.write(archive.read_bytes())
    sftp.close()

    cmd = f"""
set -e
REPO=/opt/camxora/repo
ENV=$REPO/platform_api/.env
tar -xzf /tmp/camxora-src.tar.gz -C $REPO platform_api
chown -R camxora:camxora $REPO/platform_api

# Ensure Suno callback IPs are allowlisted (HMAC may be unsigned from provider).
if grep -q '^PLATFORM_SUNO_CALLBACK_ALLOWED_IPS=' "$ENV" 2>/dev/null; then
  if ! grep '^PLATFORM_SUNO_CALLBACK_ALLOWED_IPS=' "$ENV" | grep -q '47.89.217.55'; then
    sed -i 's|^PLATFORM_SUNO_CALLBACK_ALLOWED_IPS=.*|PLATFORM_SUNO_CALLBACK_ALLOWED_IPS={SUNO_CALLBACK_IPS}|' "$ENV"
  fi
else
  echo 'PLATFORM_SUNO_CALLBACK_ALLOWED_IPS={SUNO_CALLBACK_IPS}' >> "$ENV"
fi

cd $REPO/platform_api
sudo -u camxora bash -lc 'cd /opt/camxora/repo/platform_api && source .venv/bin/activate && alembic upgrade head'
systemctl restart camxora-api
sleep 3
systemctl is-active camxora-api
echo DEPLOY_BILLING_FIXES_DONE
"""
    _stdin, stdout, stderr = client.exec_command(cmd, get_pty=True)
    out = stdout.read().decode("utf-8", errors="replace")
    err = stderr.read().decode("utf-8", errors="replace")
    print(out)
    if err.strip():
        print(err, file=sys.stderr)
    code = stdout.channel.recv_exit_status()
    client.close()
    return code


if __name__ == "__main__":
    raise SystemExit(main())
