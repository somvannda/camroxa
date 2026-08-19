#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR / ".venv" / "Lib" / "site-packages"))
sys.path.insert(0, str(SCRIPT_DIR))

from deploy import ensure_deploy_key, load_production_secrets, resolve_production_ssh, ssh_connect

PRODUCTION_HOST = "82.197.71.248"
OUT = SCRIPT_DIR.parents[1] / ".dbg" / "prod_web_music"
FILES = [
    "platform_api/routers/web_music.py",
    "platform_api/services/web_music_service.py",
]


def main() -> int:
    secrets = load_production_secrets()
    host, user, password = resolve_production_ssh(secrets)
    if host != PRODUCTION_HOST:
        raise SystemExit(f"Refusing non-production host: {host}")
    OUT.mkdir(parents=True, exist_ok=True)
    client = ssh_connect(host, user, ensure_deploy_key(), password)
    sftp = client.open_sftp()
    for rel in FILES:
        dest = OUT / Path(rel).name
        sftp.get(f"/opt/camxora/repo/{rel}", str(dest))
        print(f"saved {dest}")
    sftp.close()
    client.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
