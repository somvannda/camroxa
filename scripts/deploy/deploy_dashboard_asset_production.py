#!/usr/bin/env python3
"""Deploy the user_portal dashboard from the versioned asset.

Uploads scripts/deploy/assets/user_portal_dashboard_legacy.tsx to the dashboard
route, rebuilds user_portal and restarts camxora-portal. Keeps the detailed
quota breakdown plus a clear Total-credits block.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DEPLOY = ROOT / "scripts" / "deploy"
sys.path.insert(0, str(DEPLOY / ".venv" / "Lib" / "site-packages"))
sys.path.insert(0, str(DEPLOY))

from deploy import ensure_deploy_key, ssh_connect  # noqa: E402

PRODUCTION_HOST = "82.197.71.248"
ASSET = DEPLOY / "assets" / "user_portal_dashboard_legacy.tsx"
REMOTE_PATH = "/opt/camxora/repo/user_portal/src/app/dashboard/page.tsx"


def load_env(name: str) -> dict[str, str]:
    data: dict[str, str] = {}
    for line in (ROOT / ".deploy" / name).read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        data[key.strip()] = value.strip()
    return data


def main() -> int:
    prod = load_env("secrets.production.env")
    host = prod.get("PRODUCTION_VPS_HOST") or prod["VPS_HOST"]
    if host != PRODUCTION_HOST:
        raise SystemExit(f"Refusing non-production host: {host}")
    if not ASSET.is_file():
        raise SystemExit(f"Missing asset: {ASSET}")

    content = ASSET.read_text(encoding="utf-8")
    if "Total credits" not in content or "QuotaMeter" not in content:
        raise SystemExit("Asset does not look like the detailed dashboard")

    client = ssh_connect(
        host,
        prod.get("PRODUCTION_VPS_USER") or prod["VPS_USER"],
        ensure_deploy_key(),
        prod.get("PRODUCTION_VPS_PASSWORD") or prod.get("VPS_PASSWORD"),
    )
    try:
        sftp = client.open_sftp()
        with sftp.file(REMOTE_PATH, "wb") as rf:
            rf.write(content.encode("utf-8"))
        sftp.close()
        print(f"Uploaded dashboard asset -> {REMOTE_PATH}")
        cmd = (
            "set -e; "
            "chown camxora:camxora " + REMOTE_PATH + "; "
            "sudo -u camxora bash -lc 'cd /opt/camxora/repo/user_portal && npm run build'; "
            "systemctl restart camxora-portal; "
            "sleep 2; "
            "systemctl is-active camxora-portal; "
            "grep -c 'Total credits' " + REMOTE_PATH + "; "
            "echo DASHBOARD_ASSET_DEPLOYED"
        )
        _, stdout, stderr = client.exec_command(cmd, get_pty=True, timeout=1200)
        out = stdout.read().decode(errors="replace")
        err = stderr.read().decode(errors="replace")
        print(out.encode("ascii", errors="replace").decode("ascii"))
        if err.strip():
            print(err.encode("ascii", errors="replace").decode("ascii"), file=sys.stderr)
        if "DASHBOARD_ASSET_DEPLOYED" not in out:
            raise SystemExit("Dashboard asset deploy did not finish cleanly")
    finally:
        client.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
