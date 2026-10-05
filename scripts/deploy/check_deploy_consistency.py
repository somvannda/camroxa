#!/usr/bin/env python3
"""Check that this worktree can safely deploy platform_api to sandbox/production.

    python scripts/deploy/check_deploy_consistency.py            # production
    python scripts/deploy/check_deploy_consistency.py sandbox

Fails (non-zero) if the target DB's applied migration is not present in this
worktree's migrations, or if the worktree has multiple migration heads.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / ".venv" / "Lib" / "site-packages"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from consistency import check_consistency  # noqa: E402
from deploy import (  # noqa: E402
    ensure_deploy_key,
    load_production_secrets,
    load_sandbox_secrets,
    resolve_production_ssh,
    resolve_sandbox_ssh,
    ssh_connect,
)


def main() -> int:
    target = (sys.argv[1] if len(sys.argv) > 1 else "production").strip().lower()
    if target.startswith("s"):
        secrets = load_sandbox_secrets()
        host, user, password = resolve_sandbox_ssh(secrets)
    else:
        secrets = load_production_secrets()
        host, user, password = resolve_production_ssh(secrets)

    print(f"Checking deploy consistency for {target} ({host}) ...")
    client = ssh_connect(host, user, ensure_deploy_key(), password)
    try:
        check_consistency(client)
    finally:
        client.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
