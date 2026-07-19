#!/usr/bin/env python3
"""Deploy Suno blocklist registry (API migration + admin portal) to sandbox."""

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
sudo -u camxora bash -lc "cd $REPO/platform_api && source .venv/bin/activate && alembic upgrade head"
sudo -u postgres psql -d camxora_platform -t -A -c "SELECT version_num FROM alembic_version;"
sudo -u postgres psql -d camxora_platform -t -A -c "SELECT column_name FROM information_schema.columns WHERE table_name='songs' AND column_name IN ('suno_last_sanitize','suno_auto_retry_count');"
sudo -u postgres psql -d camxora_platform -t -A -c "SELECT COUNT(*) FROM suno_blocklist_terms;"
systemctl restart camxora-api
sleep 2
systemctl is-active camxora-api
sudo -u camxora bash -lc "cd $REPO/admin_portal && (npm ci || npm install --no-audit --no-fund) && npm run build"
systemctl restart camxora-admin 2>/dev/null || true
sleep 2
systemctl is-active camxora-admin 2>/dev/null || echo admin_service_skipped
echo SUNO_BLOCKLIST_DEPLOY_DONE
"""
    _, stdout, stderr = client.exec_command(cmd, get_pty=True)
    out = stdout.read().decode("utf-8", errors="replace")
    err = stderr.read().decode("utf-8", errors="replace")
    sys.stdout.buffer.write(out.encode("utf-8", errors="replace"))
    if err.strip():
        sys.stdout.buffer.write(err.encode("utf-8", errors="replace"))
    code = stdout.channel.recv_exit_status()
    client.close()
    return code


if __name__ == "__main__":
    raise SystemExit(main())
