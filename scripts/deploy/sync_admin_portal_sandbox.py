#!/usr/bin/env python3
"""Sync admin_portal to sandbox and rebuild."""

from __future__ import annotations

import sys
import tarfile
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / ".venv" / "Lib" / "site-packages"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from deploy import ensure_deploy_key, load_secrets, ssh_connect, tar_filter  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[2]


def main() -> int:
    secrets = load_secrets()
    client = ssh_connect(
        secrets["VPS_HOST"],
        secrets["VPS_USER"],
        ensure_deploy_key(),
        secrets.get("VPS_PASSWORD") or None,
    )
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
