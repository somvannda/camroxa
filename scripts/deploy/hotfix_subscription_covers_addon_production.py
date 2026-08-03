#!/usr/bin/env python3
"""File-scoped production hotfix: subscription coverage + addon scaling."""
from __future__ import annotations

import sys
import tarfile
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DEPLOY = ROOT / "scripts" / "deploy"
sys.path.insert(0, str(DEPLOY / ".venv" / "Lib" / "site-packages"))
sys.path.insert(0, str(DEPLOY))

from deploy import ensure_deploy_key, ssh_connect  # noqa: E402

FILES = [
    "platform_api/services/billing_mode_service.py",
    "platform_api/services/batch_service.py",
    "platform_api/services/usage_enforcement_service.py",
    "platform_api/tests/test_billing_mode_service.py",
    "docs/changelog/2026-08-02-subscription-covers-addon-scaling.md",
]

PRODUCTION_HOST = "82.197.71.248"


def load_production() -> dict[str, str]:
    data: dict[str, str] = {}
    for line in (ROOT / ".deploy" / "secrets.production.env").read_text(
        encoding="utf-8"
    ).splitlines():
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
    print(f"Target production host: {host}")

    archive = Path(tempfile.mkdtemp(prefix="covers-addon-prod-")) / "api.tar.gz"
    with tarfile.open(archive, "w:gz") as tar:
        for rel in FILES:
            path = ROOT / rel
            if not path.is_file():
                raise FileNotFoundError(path)
            tar.add(path, arcname=rel.replace("\\", "/"))

    client = ssh_connect(host, user, ensure_deploy_key(), password)
    try:
        sftp = client.open_sftp()
        with sftp.file("/tmp/covers-addon-api.tar.gz", "wb") as remote:
            remote.write(archive.read_bytes())
        sftp.close()

        cmd = (
            "set -e; "
            "REPO=/opt/camxora/repo; "
            "tar -xzf /tmp/covers-addon-api.tar.gz -C $REPO; "
            "chown -R camxora:camxora $REPO/platform_api $REPO/docs/changelog; "
            "systemctl restart camxora-api; "
            "systemctl try-restart camxora-worker 2>/dev/null || "
            "systemctl try-restart camxora-api-worker 2>/dev/null || true; "
            "sleep 2; "
            "systemctl is-active camxora-api; "
            "grep -n 'required_credits = units_to_credits' "
            "$REPO/platform_api/services/batch_service.py | head -3; "
            "grep -n 'fanout_draft_jobs' "
            "$REPO/platform_api/services/batch_service.py | head -3; "
            "grep -n 'addon_slots' "
            "$REPO/platform_api/services/billing_mode_service.py | head -8; "
            "grep -n 'attribute_secondary_daily_usage' "
            "$REPO/platform_api/services/usage_enforcement_service.py | head -3; "
            "echo COVERS_ADDON_PROD_DONE"
        )
        _, stdout, stderr = client.exec_command(cmd, get_pty=True)
        print(stdout.read().decode(errors="replace"))
        err = stderr.read().decode(errors="replace")
        if err.strip():
            print("STDERR:", err)
    finally:
        client.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
