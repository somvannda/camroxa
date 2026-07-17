#!/usr/bin/env python3
"""Ensure PLATFORM_SLAI_API_BASE_URL is set on sandbox and restart API."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / ".venv" / "Lib" / "site-packages"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from deploy import ensure_deploy_key, load_secrets, ssh_connect  # noqa: E402
from migrate_platform_config import read_local_env  # noqa: E402

SLAI_BASE_DEFAULT = "https://api.slai.shop"

REMOTE = r"""
set -e
ENV_FILE=/opt/camxora/repo/platform_api/.env
SLAI_BASE='__SLAI_BASE__'
if grep -q '^PLATFORM_SLAI_API_BASE_URL=' "$ENV_FILE"; then
  sed -i "s|^PLATFORM_SLAI_API_BASE_URL=.*|PLATFORM_SLAI_API_BASE_URL=${SLAI_BASE}|" "$ENV_FILE"
else
  echo "PLATFORM_SLAI_API_BASE_URL=${SLAI_BASE}" >> "$ENV_FILE"
fi
chown camxora:camxora "$ENV_FILE"
chmod 600 "$ENV_FILE"
grep SLAI "$ENV_FILE"
systemctl restart camxora-api
sleep 3
systemctl is-active camxora-api
echo SLAI_ENV_SYNC_DONE
"""


def main() -> int:
    local_env = read_local_env()
    slai_base = local_env.get("PLATFORM_SLAI_API_BASE_URL", SLAI_BASE_DEFAULT) or SLAI_BASE_DEFAULT
    secrets = load_secrets()
    client = ssh_connect(secrets["VPS_HOST"], secrets["VPS_USER"], ensure_deploy_key(), None)
    cmd = REMOTE.replace("__SLAI_BASE__", slai_base)
    _, stdout, stderr = client.exec_command(cmd, timeout=60)
    print(stdout.read().decode("utf-8", errors="replace"))
    err = stderr.read().decode("utf-8", errors="replace")
    if err.strip():
        print("STDERR:", err)
    code = stdout.channel.recv_exit_status()
    client.close()
    return code


if __name__ == "__main__":
    raise SystemExit(main())
