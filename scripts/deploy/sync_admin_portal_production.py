#!/usr/bin/env python3
"""Sync admin_portal to production and rebuild (user-requested production deploy)."""

from __future__ import annotations

import sys
import tarfile
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / ".venv" / "Lib" / "site-packages"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from deploy import (  # noqa: E402
    ensure_deploy_key,
    load_production_secrets,
    resolve_production_ssh,
    ssh_connect,
    tar_filter,
)

REPO_ROOT = Path(__file__).resolve().parents[2]


def main() -> int:
    secrets = load_production_secrets()
    host, user, password = resolve_production_ssh(secrets)
    print(f"Target production host: {host}")
    client = ssh_connect(host, user, ensure_deploy_key(), password)
    tmp = Path(tempfile.mkdtemp(prefix="camxora-admin-"))
    archive = tmp / "admin.tar.gz"
    with tarfile.open(archive, "w:gz") as tar:
        tar.add(REPO_ROOT / "admin_portal", arcname="admin_portal", filter=tar_filter, recursive=True)
    print(f"Uploading {archive.name} ({archive.stat().st_size / (1024 * 1024):.1f} MB)...")
    sftp = client.open_sftp()
    with sftp.file("/tmp/camxora-admin.tar.gz", "wb") as remote_file:
        remote_file.write(archive.read_bytes())
    sftp.close()

    cmd = r"""
set -e
REPO=/opt/camxora/repo
tar -xzf /tmp/camxora-admin.tar.gz -C $REPO
chown -R camxora:camxora $REPO/admin_portal
sudo -u camxora bash -lc 'cd /opt/camxora/repo/admin_portal && (npm ci || npm install --no-audit --no-fund) && npm run build'
echo ADMIN_SYNC_DONE
"""
    _, stdout, stderr = client.exec_command(cmd, get_pty=True)
    out = stdout.read().decode("utf-8", errors="replace")
    err = stderr.read().decode("utf-8", errors="replace")
    code = stdout.channel.recv_exit_status()
    client.close()
    snippet = out[-5000:] if len(out) > 5000 else out
    sys.stdout.buffer.write(snippet.encode("utf-8", errors="replace") + b"\n")
    if err.strip():
        sys.stdout.buffer.write(err[-2000:].encode("utf-8", errors="replace") + b"\n")
    return code


if __name__ == "__main__":
    raise SystemExit(main())
