#!/usr/bin/env python3
"""Apply migration 058 on sandbox and restart API (preserves .env)."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / ".venv" / "Lib" / "site-packages"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from deploy import build_source_tarball, ensure_deploy_key, load_secrets, ssh_connect  # noqa: E402


def main() -> int:
    secrets = load_secrets()
    client = ssh_connect(
        secrets["VPS_HOST"],
        secrets["VPS_USER"],
        ensure_deploy_key(),
        secrets.get("VPS_PASSWORD") or None,
    )

    archive = build_source_tarball()
    remote = "/tmp/camxora-src.tar.gz"
    sftp = client.open_sftp()
    with sftp.file(remote, "wb") as fh:
        fh.write(archive.read_bytes())
    sftp.close()

    cmd = r"""
set -e
cp /opt/camxora/repo/platform_api/.env /tmp/camxora-api.env.bak
tar -xzf /tmp/camxora-src.tar.gz -C /opt/camxora/repo
cp /tmp/camxora-api.env.bak /opt/camxora/repo/platform_api/.env
chown -R camxora:camxora /opt/camxora/repo
sudo -u camxora bash -lc 'cd /opt/camxora/repo/platform_api && source .venv/bin/activate && alembic upgrade head'
systemctl restart camxora-api
sleep 3
curl -sf https://api.sandbox.camxora.com/api/v1/auth/signup-mode
echo ""
echo MIGRATION_DONE
"""
    _, stdout, stderr = client.exec_command(cmd, timeout=120)
    print(stdout.read().decode(errors="replace"))
    err = stderr.read().decode(errors="replace").strip()
    if err:
        print(err, file=sys.stderr)
    code = stdout.channel.recv_exit_status()
    client.close()
    return code


if __name__ == "__main__":
    raise SystemExit(main())
