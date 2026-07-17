#!/usr/bin/env python3
"""Rebuild and restart user_portal on sandbox; log to deploy-rebuild.log."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / ".venv" / "Lib" / "site-packages"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from deploy import build_source_tarball, ensure_deploy_key, load_secrets, ssh_connect  # noqa: E402

LOG = Path(__file__).resolve().parent / "deploy-rebuild.log"


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
mkdir -p $REPO
tar -xzf /tmp/camxora-src.tar.gz -C $REPO
chown -R camxora:camxora /opt/camxora/repo
cat > /opt/camxora/repo/user_portal/.env.production <<'ENVEOF'
# Same-origin /api/v1 via nginx — leave NEXT_PUBLIC_PLATFORM_API_BASE_URL unset
NEXT_PUBLIC_CAMXORA_ENV=sandbox
NEXT_PUBLIC_WEBSITE_URL=https://sandbox.camxora.com
NEXT_PUBLIC_USER_PORTAL_URL=https://app.sandbox.camxora.com
ENVEOF
chown camxora:camxora /opt/camxora/repo/user_portal/.env.production
systemctl restart camxora-api
sleep 2
systemctl is-active camxora-api
sudo -u camxora bash -lc 'cd /opt/camxora/repo/user_portal && (npm ci || npm install --no-audit --no-fund) && npm run build'
systemctl restart camxora-portal
grep -n signup /opt/camxora/repo/user_portal/next.config.ts || true
echo BUILD_DONE
"""
    _, stdout, stderr = client.exec_command(cmd, get_pty=True)
    out = stdout.read().decode("utf-8", errors="replace")
    err = stderr.read().decode("utf-8", errors="replace")
    code = stdout.channel.recv_exit_status()
    client.close()

    LOG.write_text(out + "\n--- STDERR ---\n" + err + f"\n--- EXIT {code} ---\n", encoding="utf-8")
    return code


if __name__ == "__main__":
    raise SystemExit(main())
