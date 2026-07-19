#!/usr/bin/env python3
"""Sync platform_api to sandbox and restart API (no unrelated DB changes)."""

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
tar -xzf /tmp/camxora-src.tar.gz -C $REPO platform_api
chown -R camxora:camxora $REPO/platform_api
grep -q '^PLATFORM_SAMPLE_PACK_URL_IMPORT_MAX_MB=' $REPO/platform_api/.env || \
  echo 'PLATFORM_SAMPLE_PACK_URL_IMPORT_MAX_MB=1024' >> $REPO/platform_api/.env
grep '^PLATFORM_SAMPLE_PACK_URL_IMPORT_MAX_MB=' $REPO/platform_api/.env
systemctl restart camxora-api
sleep 2
systemctl is-active camxora-api
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
