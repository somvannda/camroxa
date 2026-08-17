#!/usr/bin/env python3
"""Deploy music streaming enhancements to production (API + alembic + music_web + admin).

Do not run unless the user explicitly asked for a production deploy.
"""

from __future__ import annotations

import sys
import tarfile
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / ".venv" / "Lib" / "site-packages"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from deploy import (  # noqa: E402
    build_source_tarball,
    ensure_deploy_key,
    load_production_secrets,
    resolve_production_ssh,
    ssh_connect,
    tar_filter,
)

REPO_ROOT = Path(__file__).resolve().parents[2]


def _run(client, cmd: str, *, label: str) -> int:
    print(f"\n=== {label} ===")
    transport = client.get_transport()
    if transport is None:
        raise RuntimeError("SSH transport unavailable")
    channel = transport.open_session()
    channel.get_pty()
    channel.exec_command(cmd)
    while not channel.exit_status_ready():
        if channel.recv_ready():
            sys.stdout.buffer.write(channel.recv(4096))
            sys.stdout.flush()
        if channel.recv_stderr_ready():
            sys.stderr.buffer.write(channel.recv_stderr(4096))
            sys.stderr.flush()
        time.sleep(0.2)
    while channel.recv_ready():
        sys.stdout.buffer.write(channel.recv(4096))
    while channel.recv_stderr_ready():
        sys.stderr.buffer.write(channel.recv_stderr(4096))
    code = channel.recv_exit_status()
    print(f"=== {label} exit={code} ===")
    return code


def main() -> int:
    secrets = load_production_secrets()
    host, user, password = resolve_production_ssh(secrets)
    print(f"Target production host: {host}")
    custom_key = secrets.get("PRODUCTION_VPS_SSH_KEY") or secrets.get("VPS_SSH_KEY") or None
    client = ssh_connect(
        host,
        user,
        Path(custom_key) if custom_key else ensure_deploy_key(),
        password,
    )

    try:
        archive = build_source_tarball()
        sftp = client.open_sftp()
        with sftp.file("/tmp/camxora-src.tar.gz", "wb") as remote_file:
            remote_file.write(archive.read_bytes())

        tmp = Path(tempfile.mkdtemp(prefix="camxora-admin-prod-"))
        admin_archive = tmp / "admin.tar.gz"
        with tarfile.open(admin_archive, "w:gz") as tar:
            tar.add(
                REPO_ROOT / "admin_portal",
                arcname="admin_portal",
                filter=tar_filter,
                recursive=True,
            )
        with sftp.file("/tmp/camxora-admin.tar.gz", "wb") as remote_file:
            remote_file.write(admin_archive.read_bytes())
        sftp.close()

        # 1) Sync platform_api source first so alembic sees new migrations.
        code = _run(
            client,
            r"""
set -e
REPO=/opt/camxora/repo
tar -xzf /tmp/camxora-src.tar.gz -C $REPO platform_api
chown -R camxora:camxora $REPO/platform_api
echo API_SOURCE_SYNCED
""",
            label="sync platform_api",
        )
        if code != 0:
            return code

        # 2) Alembic upgrade, then restart API.
        code = _run(
            client,
            r"""
set -e
REPO=/opt/camxora/repo
sudo -u camxora bash -lc 'cd /opt/camxora/repo/platform_api && source .venv/bin/activate && alembic upgrade head'
sudo -u postgres psql -d camxora_platform -t -A -c "SELECT version_num FROM alembic_version;"
sudo -u postgres psql -d camxora_platform -t -A -c "SELECT column_name FROM information_schema.columns WHERE table_name='suno_tasks' AND column_name LIKE 'audio_id%';"
systemctl restart camxora-api
sleep 3
systemctl is-active camxora-api
curl -sf http://127.0.0.1:8100/health >/dev/null && echo API_HEALTH_OK
echo ALEMBIC_AND_API_DONE
""",
            label="alembic + restart API",
        )
        if code != 0:
            return code

        # 3) Rebuild music_web against production API.
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

mkdir -p /etc/systemd/system/camxora-music.service.d
cat > /etc/systemd/system/camxora-music.service.d/streaming-api.conf <<UNIT
[Service]
Environment=STREAMING_API_BASE_URL=http://127.0.0.1:8100
Environment=NEXT_PUBLIC_API_BASE_URL=$API_URL
Environment=NEXT_PUBLIC_USER_PORTAL_URL=https://app.camxora.com
Environment=NEXT_PUBLIC_WEBSITE_URL=https://camxora.com
Environment=NEXT_PUBLIC_CAMXORA_ENV=production
UNIT

systemctl daemon-reload
systemctl restart camxora-music
sleep 6
systemctl is-active camxora-music
curl -sf -o /dev/null -w '%{http_code}\n' http://127.0.0.1:3102/ || true
echo MUSIC_WEB_REBUILD_DONE
""",
            label="rebuild music_web",
        )
        if code != 0:
            return code

        # 4) Admin portal (streaming pagination UI).
        code = _run(
            client,
            r"""
set -e
REPO=/opt/camxora/repo
tar -xzf /tmp/camxora-admin.tar.gz -C $REPO
chown -R camxora:camxora $REPO/admin_portal
sudo -u camxora bash -lc 'cd /opt/camxora/repo/admin_portal && (npm ci || npm install --no-audit --no-fund) && npm run build'
systemctl restart camxora-admin || true
sleep 2
systemctl is-active camxora-admin || true
echo ADMIN_SYNC_DONE
""",
            label="rebuild admin_portal",
        )
        if code != 0:
            return code

        print("\nProduction music streaming deploy finished.")
        print("  API:   https://api.camxora.com/health")
        print("  Music: https://music.camxora.com")
        print("  Admin: https://admin.camxora.com")
        return 0
    finally:
        client.close()


if __name__ == "__main__":
    raise SystemExit(main())
