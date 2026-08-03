#!/usr/bin/env python3
"""Pull production admin pipeline API modules into the local repo."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DEPLOY = ROOT / "scripts" / "deploy"
sys.path.insert(0, str(DEPLOY / ".venv" / "Lib" / "site-packages"))
sys.path.insert(0, str(DEPLOY))

from deploy import ensure_deploy_key, ssh_connect  # noqa: E402

PRODUCTION_HOST = "82.197.71.248"
FILES = [
    "platform_api/routers/admin_pipeline.py",
    "platform_api/services/admin_pipeline_service.py",
    "platform_api/services/admin_pipeline_retry_costs.py",
    "platform_api/services/pipeline_board_notifications.py",
    "platform_api/services/pipeline_waive_retry_executor.py",
]


def load_production() -> dict[str, str]:
    data: dict[str, str] = {}
    for line in (ROOT / ".deploy" / "secrets.production.env").read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        data[key.strip()] = value.strip()
    return data


def main() -> int:
    secrets = load_production()
    host = secrets.get("PRODUCTION_VPS_HOST") or secrets["VPS_HOST"]
    user = secrets.get("PRODUCTION_VPS_USER") or secrets["VPS_USER"]
    password = secrets.get("PRODUCTION_VPS_PASSWORD") or secrets.get("VPS_PASSWORD")
    if host != PRODUCTION_HOST:
        raise SystemExit(f"Refusing non-production host: {host}")
    client = ssh_connect(host, user, ensure_deploy_key(), password)
    try:
        # Also discover schema models / main includes
        _, stdout, _ = client.exec_command(
            "grep -n 'admin_pipeline\\|pipeline_board\\|AdminPipeline' "
            "/opt/camxora/repo/platform_api/main.py "
            "/opt/camxora/repo/platform_api/wire_dependencies.py "
            "/opt/camxora/repo/platform_api/models/schemas.py 2>/dev/null | head -60; "
            "grep -Rnl 'AdminPipeline\\|admin_pipeline' /opt/camxora/repo/platform_api/models "
            "/opt/camxora/repo/platform_api/dependencies.py 2>/dev/null | head -20"
        )
        print(stdout.read().decode(errors="replace"))

        sftp = client.open_sftp()
        for rel in FILES:
            remote = f"/opt/camxora/repo/{rel}"
            local = ROOT / rel
            local.parent.mkdir(parents=True, exist_ok=True)
            with sftp.file(remote, "rb") as rf:
                data = rf.read()
            local.write_bytes(data)
            print(f"Downloaded {rel} ({len(data)} bytes)")
        sftp.close()
    finally:
        client.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
