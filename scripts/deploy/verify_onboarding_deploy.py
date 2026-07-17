#!/usr/bin/env python3
"""Verify onboarding deploy on sandbox."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / ".venv" / "Lib" / "site-packages"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from deploy import ensure_deploy_key, load_secrets, ssh_connect  # noqa: E402


def main() -> int:
    client = ssh_connect(
        load_secrets()["VPS_HOST"],
        load_secrets()["VPS_USER"],
        ensure_deploy_key(),
        None,
    )
    cmd = r"""
echo '=== services ==='
systemctl is-active camxora-api camxora-portal
echo '=== portal env ==='
cat /opt/camxora/repo/user_portal/.env.production
echo '=== api resolve ==='
grep -c 'payments/resolve' /opt/camxora/repo/platform_api/routers/billing.py || true
echo '=== purple theme ==='
grep -c 'from-violet-500' /opt/camxora/repo/user_portal/src/components/onboarding/onboarding-plan-picker.tsx || true
echo '=== onboarding https ==='
curl -sI https://app.sandbox.camxora.com/onboarding | head -2
"""
    _, stdout, stderr = client.exec_command(cmd)
    print(stdout.read().decode("utf-8", errors="replace"))
    err = stderr.read().decode("utf-8", errors="replace")
    if err.strip():
        print(err)
    client.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
