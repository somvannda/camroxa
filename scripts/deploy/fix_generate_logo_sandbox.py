#!/usr/bin/env python3
"""Fix generate-logo 504 on sandbox: nginx API timeouts + SLAI routing for channel images."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / ".venv" / "Lib" / "site-packages"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from apply_nginx import apply_remote, upload_conf  # noqa: E402
from deploy import ensure_deploy_key, load_secrets, ssh_connect  # noqa: E402
from migrate_ai_routing_sandbox import main as migrate_routing  # noqa: E402


def main() -> int:
    secrets = load_secrets()
    client = ssh_connect(secrets["VPS_HOST"], secrets["VPS_USER"], ensure_deploy_key(), None)
    print("=== Applying nginx API timeouts ===")
    upload_conf(client, "sandbox")
    out, err = apply_remote(client, "sandbox")
    print(out)
    if err.strip():
        print(err)
    client.close()

    print("=== Patching channel_logo/cover routing ===")
    return migrate_routing()


if __name__ == "__main__":
    raise SystemExit(main())
