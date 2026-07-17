#!/usr/bin/env python3
"""Rebuild user portal + website on sandbox and restart services."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / ".venv" / "Lib" / "site-packages"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from deploy import build_source_tarball, ensure_deploy_key, load_secrets, ssh_connect  # noqa: E402


def upload_source(client) -> None:
    archive = build_source_tarball()
    remote_path = "/tmp/camxora-src.tar.gz"
    sftp = client.open_sftp()
    with sftp.file(remote_path, "wb") as remote_file:
        remote_file.write(archive.read_bytes())
    sftp.close()
    _, stdout, stderr = client.exec_command(
        "mkdir -p /opt/camxora/repo && "
        "tar -xzf /tmp/camxora-src.tar.gz -C /opt/camxora/repo && "
        "chown -R camxora:camxora /opt/camxora/repo"
    )
    stdout.channel.recv_exit_status()
    err = stderr.read().decode("utf-8", errors="replace").strip()
    if err:
        print(err)


def main() -> int:
    secrets = load_secrets()
    client = ssh_connect(secrets["VPS_HOST"], secrets["VPS_USER"], ensure_deploy_key(), None)

    upload_source(client)

    cmd = r"""
set -e
REPO=/opt/camxora/repo
cat > $REPO/user_portal/.env.production <<'ENVEOF'
# Same-origin /api/v1 via nginx — leave NEXT_PUBLIC_PLATFORM_API_BASE_URL unset
NEXT_PUBLIC_CAMXORA_ENV=sandbox
NEXT_PUBLIC_WEBSITE_URL=https://sandbox.camxora.com
NEXT_PUBLIC_USER_PORTAL_URL=https://app.sandbox.camxora.com
ENVEOF
cat > $REPO/website/.env.production <<'ENVEOF'
NEXT_PUBLIC_PLATFORM_API_BASE_URL=https://api.sandbox.camxora.com/api/v1
NEXT_PUBLIC_CAMXORA_ENV=sandbox
NEXT_PUBLIC_SITE_URL=https://sandbox.camxora.com
NEXT_PUBLIC_USER_PORTAL_URL=https://app.sandbox.camxora.com
ENVEOF
chown camxora:camxora $REPO/user_portal/.env.production $REPO/website/.env.production
for app in user_portal website; do
  sudo -u camxora bash -lc "cd $REPO/$app && npm ci || npm install --no-audit --no-fund && npm run build"
done
systemctl restart camxora-portal camxora-website
echo DONE
"""
    _, stdout, stderr = client.exec_command(cmd)
    print(stdout.read().decode("utf-8", errors="replace"))
    print(stderr.read().decode("utf-8", errors="replace"))
    code = stdout.channel.recv_exit_status()
    client.close()
    return code


if __name__ == "__main__":
    raise SystemExit(main())
