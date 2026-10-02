#!/usr/bin/env python3
"""READ-ONLY: pull live prod streaming_upload_service.py for exact patch anchors."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DEPLOY = ROOT / "scripts" / "deploy"
LOCAL = ROOT / ".dbg" / "live-probe" / "streaming_upload_service.live2.py"
sys.path.insert(0, str(DEPLOY / ".venv" / "Lib" / "site-packages"))
sys.path.insert(0, str(DEPLOY))

from deploy import ensure_deploy_key, load_production_secrets, resolve_production_ssh, ssh_connect  # noqa: E402

PRODUCTION_HOST = "82.197.71.248"
REMOTE = "/opt/camxora/repo/platform_api/services/streaming_upload_service.py"


def main() -> int:
    secrets = load_production_secrets()
    host, user, password = resolve_production_ssh(secrets)
    if host != PRODUCTION_HOST:
        raise SystemExit(f"Refusing non-production host: {host}")
    print(f"=== pull live streaming_upload_service.py from {host} ===")
    client = ssh_connect(host, user, ensure_deploy_key(), password)
    try:
        sftp = client.open_sftp()
        sftp.get(REMOTE, str(LOCAL))
        sftp.close()
        print(f"OK saved {LOCAL} ({LOCAL.stat().st_size} bytes)")
        return 0
    finally:
        client.close()


if __name__ == "__main__":
    raise SystemExit(main())
