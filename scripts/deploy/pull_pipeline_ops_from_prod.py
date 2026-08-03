#!/usr/bin/env python3
"""Download production admin Pipeline Ops sources into the local repo."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DEPLOY = ROOT / "scripts" / "deploy"
sys.path.insert(0, str(DEPLOY / ".venv" / "Lib" / "site-packages"))
sys.path.insert(0, str(DEPLOY))

from deploy import ensure_deploy_key, ssh_connect  # noqa: E402

PRODUCTION_HOST = "82.197.71.248"
REMOTE_FILES = [
    "admin_portal/src/hooks/use-pipeline-ops.ts",
    "admin_portal/src/types/pipeline.ts",
    "admin_portal/src/pages/pipeline/index.tsx",
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
        # Discover all pipeline page files
        _, stdout, _ = client.exec_command(
            "find /opt/camxora/repo/admin_portal/src/pages/pipeline -type f | sort; "
            "ls -la /opt/camxora/repo/admin_portal/src/hooks/use-pipeline-ops.ts "
            "/opt/camxora/repo/admin_portal/src/types/pipeline.ts; "
            "grep -n 'pipeline\\|Pipeline' /opt/camxora/repo/admin_portal/src/App.tsx "
            "/opt/camxora/repo/admin_portal/src/components/layout/top-bar.tsx 2>/dev/null | head -40"
        )
        listing = stdout.read().decode(errors="replace")
        print(listing)

        sftp = client.open_sftp()
        files = list(REMOTE_FILES)
        for line in listing.splitlines():
            line = line.strip()
            if line.startswith("/opt/camxora/repo/admin_portal/src/pages/pipeline/"):
                rel = line[len("/opt/camxora/repo/") :]
                if rel not in files:
                    files.append(rel)

        for rel in files:
            remote = f"/opt/camxora/repo/{rel}"
            local = ROOT / rel
            local.parent.mkdir(parents=True, exist_ok=True)
            try:
                with sftp.file(remote, "rb") as rf:
                    data = rf.read()
                local.write_bytes(data)
                print(f"Downloaded {rel} ({len(data)} bytes)")
            except FileNotFoundError:
                print(f"MISSING {rel}")
        sftp.close()
    finally:
        client.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
