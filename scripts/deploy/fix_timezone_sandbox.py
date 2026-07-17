#!/usr/bin/env python3
"""Deploy timezone fixes: platform_api + admin portal + audit log correction."""

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
    sftp.close()

    cmd = r"""
set -e
REPO=/opt/camxora/repo
tar -xzf /tmp/camxora-src.tar.gz -C $REPO platform_api admin_portal
chown -R camxora:camxora $REPO/platform_api $REPO/admin_portal

echo '=== Correct historical audit log timestamps (+7h) ==='
sudo -u postgres psql -d camxora_platform <<'SQL'
UPDATE audit_logs
SET created_at = created_at + interval '7 hours'
WHERE created_at < TIMESTAMPTZ '2026-07-16 16:00:00+07';
SQL

echo '=== Restart API ==='
systemctl restart camxora-api
sleep 2
systemctl is-active camxora-api

echo '=== Rebuild admin portal ==='
sudo -u camxora bash -lc "cd $REPO/admin_portal && (npm ci || npm install --no-audit --no-fund) && npm run build"

echo '=== Sample audit timestamps ==='
sudo -u postgres psql -d camxora_platform -c "SELECT created_at FROM audit_logs ORDER BY created_at DESC LIMIT 3;"
echo TIMEZONE_FIX_DONE
"""
    _, stdout, stderr = client.exec_command(cmd, get_pty=True)
    out = stdout.read().decode("utf-8", errors="replace")
    err = stderr.read().decode("utf-8", errors="replace")
    print(out)
    if err.strip():
        print(err)
    code = stdout.channel.recv_exit_status()
    client.close()
    return 0 if "TIMEZONE_FIX_DONE" in out else code


if __name__ == "__main__":
    raise SystemExit(main())
