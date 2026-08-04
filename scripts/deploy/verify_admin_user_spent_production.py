#!/usr/bin/env python3
"""Verify User Spent landed on production."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DEPLOY = ROOT / "scripts" / "deploy"
sys.path.insert(0, str(DEPLOY / ".venv" / "Lib" / "site-packages"))
sys.path.insert(0, str(DEPLOY))

from deploy import ensure_deploy_key, ssh_connect  # noqa: E402

PRODUCTION_HOST = "82.197.71.248"


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
        cmd = r"""
set -e
systemctl is-active camxora-api
test -f /opt/camxora/repo/admin_portal/src/pages/user-spent/index.tsx && echo USER_SPENT_PAGE_OK
test -f /opt/camxora/repo/platform_api/services/user_spend_service.py && echo USER_SPEND_SVC_OK
grep -n "user-spent\|UserSpent\|user_spend" /opt/camxora/repo/admin_portal/src/App.tsx /opt/camxora/repo/platform_api/routers/admin.py /opt/camxora/repo/platform_api/wire_dependencies.py | head -30
stat -c '%y %n' /opt/camxora/repo/admin_portal/dist/index.html 2>/dev/null || echo NO_DIST
echo VERIFY_DONE
"""
        _, stdout, stderr = client.exec_command(cmd, get_pty=True)
        out = stdout.read().decode(errors="replace")
        sys.stdout.buffer.write(out.encode("utf-8", errors="replace"))
        err = stderr.read().decode(errors="replace")
        if err.strip():
            sys.stderr.buffer.write(err.encode("utf-8", errors="replace"))
        return 0 if "VERIFY_DONE" in out and "USER_SPENT_PAGE_OK" in out else 1
    finally:
        client.close()


if __name__ == "__main__":
    raise SystemExit(main())
