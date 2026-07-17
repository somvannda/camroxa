#!/usr/bin/env python3
"""Sync PLATFORM_ENCRYPTION_MASTER_KEY from local .env to sandbox and restart API."""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).resolve().parent / ".venv" / "Lib" / "site-packages"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from deploy import ensure_deploy_key, load_secrets, ssh_connect  # noqa: E402
from migrate_platform_config import read_local_env, sync_encryption_key  # noqa: E402


def main() -> int:
    local_env = read_local_env()
    secrets = load_secrets()
    master_key = secrets.get("PLATFORM_ENCRYPTION_MASTER_KEY") or local_env.get(
        "PLATFORM_ENCRYPTION_MASTER_KEY", ""
    )
    if not master_key:
        print("No PLATFORM_ENCRYPTION_MASTER_KEY in local platform_api/.env or .deploy/secrets.env")
        return 1

    client = ssh_connect(secrets["VPS_HOST"], secrets["VPS_USER"], ensure_deploy_key(), None)
    try:
        print("Syncing encryption master key to sandbox...")
        sync_encryption_key(client, master_key)
    finally:
        client.close()

    print("Done. API keys should decrypt correctly now.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
