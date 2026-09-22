#!/usr/bin/env python3
"""READ-ONLY: pull prod platform_api streaming files to diff eras against local main."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DEPLOY = ROOT / "scripts" / "deploy"
DBG = ROOT / ".dbg" / "prod-stream-src"
sys.path.insert(0, str(DEPLOY / ".venv" / "Lib" / "site-packages"))
sys.path.insert(0, str(DEPLOY))

from deploy import ensure_deploy_key, load_production_secrets, resolve_production_ssh, ssh_connect  # noqa: E402

PRODUCTION_HOST = "82.197.71.248"
FILES = [
    "platform_api/routers/streaming_admin.py",
    "platform_api/services/streaming_upload_service.py",
    "platform_api/repositories/streaming_repo.py",
    "platform_api/dependencies.py",
    "platform_api/main.py",
    "admin_portal/src/hooks/use-streaming.ts",
    "admin_portal/src/pages/streaming/upload-jobs.tsx",
    "admin_portal/package.json",
    "admin_portal/src/lib/http-client.ts",
]


def main() -> int:
    secrets = load_production_secrets()
    host, user, password = resolve_production_ssh(secrets)
    if host != PRODUCTION_HOST:
        raise SystemExit(f"Refusing non-production host: {host}")
    print(f"=== pull prod streaming sources from {host} ===")
    client = ssh_connect(host, user, ensure_deploy_key(), password)
    try:
        DBG.mkdir(parents=True, exist_ok=True)
        sftp = client.open_sftp()
        for rel in FILES:
            remote = f"/opt/camxora/repo/{rel}"
            target = DBG / rel.replace("/", "__")
            try:
                sftp.get(remote, str(target))
                print(f"OK   {rel} -> {target.name}")
            except FileNotFoundError:
                print(f"MISS {rel}")
        sftp.close()
        return 0
    finally:
        client.close()


if __name__ == "__main__":
    raise SystemExit(main())
