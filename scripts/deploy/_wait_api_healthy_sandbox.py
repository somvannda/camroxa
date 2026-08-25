"""Confirm migration 117 on disk, restart API, wait for healthy."""

from __future__ import annotations

import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

DEPLOY = Path(__file__).resolve().parent
sys.path.insert(0, str(DEPLOY / ".venv" / "Lib" / "site-packages"))
sys.path.insert(0, str(DEPLOY))

from deploy import ensure_deploy_key, load_sandbox_secrets, resolve_sandbox_ssh, ssh_connect  # noqa: E402


def hit(url: str) -> str:
    try:
        with urllib.request.urlopen(url, timeout=15) as resp:
            return f"{resp.status} {resp.read(160).decode('utf-8', 'replace')}"
    except urllib.error.HTTPError as exc:
        return f"{exc.code} {exc.read(180).decode('utf-8', 'replace')}"
    except Exception as exc:  # noqa: BLE001
        return f"ERR {exc}"


def main() -> int:
    secrets = load_sandbox_secrets()
    host, user, password = resolve_sandbox_ssh(secrets)
    client = ssh_connect(host, user, ensure_deploy_key(), password)
    try:
        cmd = r"""
set +e
REPO=/opt/camxora/repo
echo FILES:
ls "$REPO/platform_api/migrations/versions" | grep -E '116_|117_'
echo ALEMBIC:
sudo -u postgres psql -d camxora_platform -t -A -c "SELECT version_num FROM alembic_version;"
sudo systemctl stop camxora-api.service
sleep 2
sudo fuser -k 8100/tcp >/dev/null 2>&1 || true
sleep 1
sudo systemctl start camxora-api.service
"""
        _, stdout, _ = client.exec_command(cmd, get_pty=True, timeout=60)
        text = stdout.read().decode("utf-8", errors="replace")
        sys.stdout.buffer.write(text.encode("utf-8", errors="replace") + b"\n")
    finally:
        client.close()

    for i in range(20):
        time.sleep(3)
        result = hit("https://api.sandbox.camxora.com/health")
        print(f"try{i+1}: {result[:200]}")
        if result.startswith("200"):
            print("PLANS", hit("https://api.sandbox.camxora.com/api/v3/plans/public")[:200])
            print("ME_CREDITS_UNAUTH", hit("https://api.sandbox.camxora.com/api/v3/me/credits")[:200])
            return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
