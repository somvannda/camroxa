#!/usr/bin/env python3
"""Pull sandbox API logs for /api/v2/subscriptions/purchase 500."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DEPLOY = ROOT / "scripts" / "deploy"
SIBLING_VENV = ROOT.parent / "MusicGenerator" / "scripts" / "deploy" / ".venv" / "Lib" / "site-packages"
for candidate in (DEPLOY / ".venv" / "Lib" / "site-packages", SIBLING_VENV):
    if candidate.is_dir():
        sys.path.insert(0, str(candidate))
        break
sys.path.insert(0, str(DEPLOY))

from deploy import ensure_deploy_key, load_sandbox_secrets, resolve_sandbox_ssh, ssh_connect  # noqa: E402

SANDBOX_HOST = "46.250.235.83"


def main() -> int:
    secrets = load_sandbox_secrets()
    host, user, password = resolve_sandbox_ssh(secrets)
    if host != SANDBOX_HOST:
        raise SystemExit(f"Refusing non-sandbox host: {host}")
    client = ssh_connect(host, user, ensure_deploy_key(), password)
    cmd = r"""
echo '--- journal around 20:03:52 ---'
journalctl -u camxora-api --since '2026-08-17 20:03:50' --until '2026-08-17 20:04:10' --no-pager
echo '--- pending subs ---'
sudo -u postgres psql -d camxora_platform -c "SELECT id, user_id, status, plan_id, external_subscription_id, created_at FROM web_subscriptions WHERE user_id='d8482b20-33c3-49b3-936d-763f13925308';"
"""
    _, stdout, stderr = client.exec_command(cmd, timeout=60)
    print(stdout.read().decode("utf-8", errors="replace"))
    err = stderr.read().decode("utf-8", errors="replace")
    if err.strip():
        print(err)
    client.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
