#!/usr/bin/env python3
"""Sync platform_api to sandbox and restart API (no unrelated DB changes)."""

from __future__ import annotations

import sys
import tarfile
import tempfile
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

REPO_ROOT = Path(__file__).resolve().parents[2]
SYSTEMD_DIR = REPO_ROOT / "scripts" / "deploy" / "systemd"
UNIT_NAMES = (
    "camxora-worker-draft@.service",
    "camxora-worker-suno@.service",
    "camxora-worker-images@.service",
)


def main() -> int:
    secrets = load_sandbox_secrets()
    host, user, password = resolve_sandbox_ssh(secrets)
    print(f"Target sandbox host: {host}")
    client = ssh_connect(host, user, ensure_deploy_key(), password)

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

    cmd = r"""
set -e
REPO=/opt/camxora/repo
tar -xzf /tmp/camxora-src.tar.gz -C $REPO platform_api
mkdir -p $REPO/scripts/deploy/systemd
tar -xzf /tmp/camxora-worker-units.tar.gz -C $REPO
chown -R camxora:camxora $REPO/platform_api $REPO/scripts/deploy/systemd
grep -q '^PLATFORM_SAMPLE_PACK_URL_IMPORT_MAX_MB=' $REPO/platform_api/.env || \
  echo 'PLATFORM_SAMPLE_PACK_URL_IMPORT_MAX_MB=1024' >> $REPO/platform_api/.env
grep '^PLATFORM_SAMPLE_PACK_URL_IMPORT_MAX_MB=' $REPO/platform_api/.env
# Single-admin: credit adjusts apply immediately (0 disables dual-control queue).
if grep -q '^PLATFORM_ADMIN_ADJUST_DUAL_CONTROL_CREDITS=' $REPO/platform_api/.env; then
  sed -i 's/^PLATFORM_ADMIN_ADJUST_DUAL_CONTROL_CREDITS=.*/PLATFORM_ADMIN_ADJUST_DUAL_CONTROL_CREDITS=0/' $REPO/platform_api/.env
else
  echo 'PLATFORM_ADMIN_ADJUST_DUAL_CONTROL_CREDITS=0' >> $REPO/platform_api/.env
fi
grep '^PLATFORM_ADMIN_ADJUST_DUAL_CONTROL_CREDITS=' $REPO/platform_api/.env
systemctl restart camxora-api
# Refresh stage worker unit files (worker name labels) then restart workers.
install -m 644 $REPO/scripts/deploy/systemd/camxora-worker-draft@.service /etc/systemd/system/camxora-worker-draft@.service
install -m 644 $REPO/scripts/deploy/systemd/camxora-worker-suno@.service /etc/systemd/system/camxora-worker-suno@.service
install -m 644 $REPO/scripts/deploy/systemd/camxora-worker-images@.service /etc/systemd/system/camxora-worker-images@.service
systemctl daemon-reload
# Draft/Suno jobs run in worker processes; restart them so they load synced code.
systemctl list-units 'camxora-worker*' --type=service --state=running,failed,inactive --no-pager --no-legend \
  | awk '{print $1}' | while read -r unit; do
  case "$unit" in
    *.service)
      systemctl restart "$unit" || true
      ;;
  esac
done
sleep 2
systemctl is-active camxora-api
systemctl list-units 'camxora-worker*' --type=service --state=running --no-pager --no-legend \
  | awk '{print $1, $4}' | head -20
grep -E 'CAMXORA_WORKER_NAME' /etc/systemd/system/camxora-worker-images@.service || true
echo API_SYNC_DONE
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
