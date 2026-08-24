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
SQL = r"""
set -e
sudo -u postgres psql -d camxora_platform -P pager=off -c "\d plans" | head -80
sudo -u postgres psql -d camxora_platform -P pager=off -c "
SELECT column_name FROM information_schema.columns WHERE table_name='licenses' ORDER BY 1;
"
sudo -u postgres psql -d camxora_platform -P pager=off -c "
SELECT p.name, p.plan_kind, p.price_cents, count(*) 
FROM licenses l JOIN plans p ON p.id=l.plan_id
GROUP BY 1,2,3 ORDER BY 4 DESC LIMIT 30;
"
echo SQL2_DONE
"""
def main():
    secrets = load_sandbox_secrets()
    host, user, password = resolve_sandbox_ssh(secrets)
    if host != SANDBOX_HOST:
        raise SystemExit("bad host")
    client = ssh_connect(host, user, ensure_deploy_key(), password)
    try:
        _, stdout, stderr = client.exec_command(SQL, get_pty=True, timeout=60)
        print(stdout.read().decode("utf-8", "replace"))
        err=stderr.read().decode("utf-8","replace")
        if err.strip(): print(err)
    finally:
        client.close()
if __name__ == "__main__":
    raise SystemExit(main())
