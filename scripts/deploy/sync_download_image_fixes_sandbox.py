#!/usr/bin/env python3
"""Deploy download queue + image sync fixes to sandbox."""

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
mkdir -p /opt/camxora/data/image-output-cache
chown -R camxora:camxora /opt/camxora/data/image-output-cache
grep -q '^PLATFORM_IMAGE_OUTPUT_CACHE_DIR=' $REPO/platform_api/.env || \
  echo 'PLATFORM_IMAGE_OUTPUT_CACHE_DIR=/opt/camxora/data/image-output-cache' >> $REPO/platform_api/.env
systemctl restart camxora-api
sleep 2
systemctl is-active camxora-api
echo DOWNLOAD_IMAGE_FIX_DEPLOY_DONE
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
