"""File-scoped production hotfix for multi-channel quota charging."""
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
    "platform_api/repositories/usage_tracking_repo.py",
    "platform_api/services/usage_enforcement_service.py",
    "platform_api/services/batch_service.py",
    "platform_api/services/quota_display_service.py",
    "platform_api/models/schemas.py",
    "platform_api/routers/credits.py",
    "platform_api/CHANGELOG.md",
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

    archive = Path(tempfile.mkdtemp(prefix="quota-hotfix-prod-")) / "quota-api.tar.gz"
    with tarfile.open(archive, "w:gz") as tar:
        for rel in FILES:
            path = ROOT / rel
            if not path.is_file():
                raise FileNotFoundError(path)
            tar.add(path, arcname=rel.replace("\\", "/"))

    client = ssh_connect(host, user, ensure_deploy_key(), password)
    try:
        sftp = client.open_sftp()
        with sftp.file("/tmp/quota-api.tar.gz", "wb") as remote:
            remote.write(archive.read_bytes())
        sftp.close()

        cmd = (
            "set -e; "
            "REPO=/opt/camxora/repo; "
            "tar -xzf /tmp/quota-api.tar.gz -C $REPO; "
            "chown -R camxora:camxora $REPO/platform_api; "
            "systemctl restart camxora-api; "
            "sleep 2; "
            "systemctl is-active camxora-api; "
            "grep -n attribute_secondary_daily_usage "
            "$REPO/platform_api/services/usage_enforcement_service.py | head -3; "
            "echo QUOTA_PROD_HOTFIX_DONE"
        )
        _, stdout, stderr = client.exec_command(cmd, get_pty=True)
        print(stdout.read().decode())
        err = stderr.read().decode()
        if err.strip():
            print("STDERR", err[-2000:])
    finally:
        client.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
