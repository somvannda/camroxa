#!/usr/bin/env python3
"""READ-ONLY: pull live prod files relevant to downloads (web_music router + service)."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DEPLOY = ROOT / "scripts" / "deploy"
DBG = ROOT / ".dbg" / "live-probe"
sys.path.insert(0, str(DEPLOY / ".venv" / "Lib" / "site-packages"))
sys.path.insert(0, str(DEPLOY))

from deploy import ensure_deploy_key, load_production_secrets, resolve_production_ssh, ssh_connect  # noqa: E402

PRODUCTION_HOST = "82.197.71.248"
FILES = [
    "platform_api/routers/web_music.py",
    "platform_api/services/web_music_service.py",
]


def main() -> int:
    secrets = load_production_secrets()
    host, user, password = resolve_production_ssh(secrets)
    if host != PRODUCTION_HOST:
        raise SystemExit(f"Refusing non-production host: {host}")
    print(f"=== pull live download-related files from {host} ===")
    client = ssh_connect(host, user, ensure_deploy_key(), password)
    try:
        DBG.mkdir(parents=True, exist_ok=True)
        sftp = client.open_sftp()
        for rel in FILES:
            remote = f"/opt/camxora/repo/{rel}"
            target = DBG / ("live__" + rel.replace("/", "__"))
            try:
                sftp.get(remote, str(target))
                print(f"OK   {rel} -> {target.name} ({target.stat().st_size} bytes)")
            except FileNotFoundError:
                print(f"MISS {rel}")
        sftp.close()
        return 0
    finally:
        client.close()


if __name__ == "__main__":
    raise SystemExit(main())
