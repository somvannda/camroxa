"""Inspect sandbox user_spend_service for the missing repo method."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DEPLOY = ROOT / "scripts" / "deploy"
sys.path.insert(0, str(DEPLOY / ".venv" / "Lib" / "site-packages"))
sys.path.insert(0, str(DEPLOY))

from deploy import ensure_deploy_key, ssh_connect  # noqa: E402

SANDBOX_HOST = "46.250.235.83"


def load_sandbox() -> dict[str, str]:
    for root in (ROOT, Path(r"G:\Developments\Projects\Camxora\MusicGenerator")):
        path = root / ".deploy" / "secrets.sandbox.env"
        if path.is_file():
            break
    else:
        raise SystemExit("No secrets.sandbox.env")
    data: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        data[key.strip()] = value.strip()
    return data


def main() -> int:
    secrets = load_sandbox()
    host = secrets.get("SANDBOX_VPS_HOST") or secrets["VPS_HOST"]
    if host != SANDBOX_HOST:
        raise SystemExit(f"Refusing non-sandbox host: {host}")
    client = ssh_connect(
        host,
        secrets.get("SANDBOX_VPS_USER") or secrets["VPS_USER"],
        ensure_deploy_key(),
        secrets.get("SANDBOX_VPS_PASSWORD") or secrets.get("VPS_PASSWORD"),
    )
    try:
        cmd = r"""
set -e
if ip -4 addr | grep -q '82.197.71.248'; then echo REFUSE_PROD; exit 1; fi
echo '--- grep service ---'
grep -n "list_web_subscriptions_for_users\\|list_active_plans_for_users" /opt/camxora/repo/platform_api/services/user_spend_service.py || true
echo '--- context ---'
grep -n -C 8 "list_web_subscriptions_for_users" /opt/camxora/repo/platform_api/services/user_spend_service.py || true
echo '--- grep repo ---'
grep -n "list_web_subscriptions_for_users\\|list_active_plans_for_users" /opt/camxora/repo/platform_api/repositories/credit_repo.py || true
echo '--- md5 ---'
md5sum /opt/camxora/repo/platform_api/services/user_spend_service.py /opt/camxora/repo/platform_api/repositories/credit_repo.py
"""
        _, stdout, stderr = client.exec_command(cmd, get_pty=True, timeout=60)
        print(stdout.read().decode("utf-8", "replace"))
        err = stderr.read().decode("utf-8", "replace")
        if err.strip():
            print(err)
    finally:
        client.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
