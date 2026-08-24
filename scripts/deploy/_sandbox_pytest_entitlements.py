#!/usr/bin/env python3
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
from deploy import ensure_deploy_key, load_sandbox_secrets, resolve_sandbox_ssh, ssh_connect
SANDBOX_HOST = "46.250.235.83"
CMD = r"""
set -e
cd /opt/camxora/repo
sudo -u camxora bash -lc 'cd /opt/camxora/repo && (test -d platform_api/.venv && . platform_api/.venv/bin/activate; python -m pytest platform_api/tests/test_subscription_entitlement_service.py -q --tb=short)'
echo PYTEST_DONE
"""
def main():
    secrets = load_sandbox_secrets()
    host, user, password = resolve_sandbox_ssh(secrets)
    if host != SANDBOX_HOST:
        raise SystemExit("bad host")
    client = ssh_connect(host, user, ensure_deploy_key(), password)
    try:
        _, stdout, stderr = client.exec_command(CMD, get_pty=True, timeout=180)
        print(stdout.read().decode("utf-8", "replace"))
        err=stderr.read().decode("utf-8","replace")
        if err.strip(): print(err)
    finally:
        client.close()
if __name__ == "__main__":
    raise SystemExit(main())
