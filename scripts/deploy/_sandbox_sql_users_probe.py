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
sudo -u postgres psql -d camxora_platform -P pager=off -c "
SELECT u.id::text, left(u.email, 40) AS email, coalesce(p.name,'') AS plan
FROM users u
LEFT JOIN licenses l ON l.user_id = u.id AND l.status = 'active'
LEFT JOIN plans p ON p.id = l.plan_id
ORDER BY u.created_at DESC NULLS LAST
LIMIT 15;
"
sudo -u postgres psql -d camxora_platform -P pager=off -c "
SELECT table_name FROM information_schema.tables
WHERE table_schema='public' AND table_name ILIKE '%addon%' OR table_name ILIKE '%entitle%'
ORDER BY 1;
"
echo SQL_DONE
"""

def main() -> int:
    secrets = load_sandbox_secrets()
    host, user, password = resolve_sandbox_ssh(secrets)
    if host != SANDBOX_HOST:
        raise SystemExit(f"Refusing non-sandbox host: {host}")
    client = ssh_connect(host, user, ensure_deploy_key(), password)
    try:
        _, stdout, stderr = client.exec_command(SQL, get_pty=True, timeout=60)
        out = stdout.read().decode("utf-8", errors="replace")
        err = stderr.read().decode("utf-8", errors="replace")
        print(out)
        if err.strip():
            print(err)
    finally:
        client.close()
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
