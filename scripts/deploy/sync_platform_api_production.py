#!/usr/bin/env python3
"""Sync platform_api to production and restart API (user-requested production deploy)."""

from __future__ import annotations

import sys
import tarfile
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / ".venv" / "Lib" / "site-packages"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from deploy import (  # noqa: E402
    PRUNE_LEFTOVER_ALEMBIC_REMOTE,
    build_source_tarball,
    ensure_deploy_key,
    load_production_secrets,
    resolve_production_ssh,
    ssh_connect,
)
from consistency import check_consistency  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[2]
SYSTEMD_DIR = REPO_ROOT / "scripts" / "deploy" / "systemd"
UNIT_NAMES = (
    "camxora-worker-draft@.service",
    "camxora-worker-suno@.service",
    "camxora-worker-images@.service",
)
PRODUCTION_HOST = "82.197.71.248"


def main() -> int:
    secrets = load_production_secrets()
    host, user, password = resolve_production_ssh(secrets)
    if host != PRODUCTION_HOST:
        raise SystemExit(f"Refusing non-production host: {host}")
    print(f"Target production host: {host}")
    client = ssh_connect(host, user, ensure_deploy_key(), password)
    check_consistency(client)

    archive = build_source_tarball()
    units_archive = Path(tempfile.mkdtemp(prefix="camxora-units-")) / "units.tar.gz"
    with tarfile.open(units_archive, "w:gz") as tar:
        for name in UNIT_NAMES:
            path = SYSTEMD_DIR / name
            tar.add(path, arcname=f"scripts/deploy/systemd/{name}")

    sftp = client.open_sftp()
    with sftp.file("/tmp/camxora-src.tar.gz", "wb") as remote_file:
        remote_file.write(archive.read_bytes())
    with sftp.file("/tmp/camxora-worker-units.tar.gz", "wb") as remote_file:
        remote_file.write(units_archive.read_bytes())
    sftp.close()

    cmd = (
        r"""
set -e
REPO=/opt/camxora/repo
tar -xzf /tmp/camxora-src.tar.gz -C $REPO platform_api
"""
        + PRUNE_LEFTOVER_ALEMBIC_REMOTE
        + r"""
mkdir -p $REPO/scripts/deploy/systemd
tar -xzf /tmp/camxora-worker-units.tar.gz -C $REPO
chown -R camxora:camxora $REPO/platform_api $REPO/scripts/deploy/systemd
systemctl restart camxora-api
# Refresh stage worker unit labels, then restart workers so new code + names load.
install -m 644 $REPO/scripts/deploy/systemd/camxora-worker-draft@.service /etc/systemd/system/camxora-worker-draft@.service
install -m 644 $REPO/scripts/deploy/systemd/camxora-worker-suno@.service /etc/systemd/system/camxora-worker-suno@.service
install -m 644 $REPO/scripts/deploy/systemd/camxora-worker-images@.service /etc/systemd/system/camxora-worker-images@.service
systemctl daemon-reload
systemctl list-units --type=service --all --no-pager --plain 'camxora-worker*' \
  | awk '{print $1}' \
  | grep -E '^camxora-worker' \
  | while read -r unit; do
      systemctl restart "$unit" || true
    done
sleep 2
systemctl is-active camxora-api
systemctl list-units 'camxora-worker*' --type=service --state=running --no-pager --no-legend \
  | awk '{print $1, $4}' | head -20
grep -E 'CAMXORA_WORKER_NAME' /etc/systemd/system/camxora-worker-images@.service || true
echo API_SYNC_DONE
"""
    )
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
