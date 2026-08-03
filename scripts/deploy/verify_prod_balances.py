#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / ".venv" / "Lib" / "site-packages"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from deploy import (  # noqa: E402
    ensure_deploy_key,
    load_production_secrets,
    resolve_production_ssh,
    ssh_connect,
)


def main() -> int:
    secrets = load_production_secrets()
    host, user, password = resolve_production_ssh(secrets)
    client = ssh_connect(host, user, ensure_deploy_key(), password)
    cmd = r"""
sleep 15
curl -s -o /dev/null -w 'HEALTH_LOCAL_%{http_code}\n' --max-time 10 http://127.0.0.1:8000/health || true
curl -s -o /dev/null -w 'HEALTH_API_%{http_code}\n' --max-time 10 https://api.camxora.com/health || true
# unauth should be 401/403 not 404
curl -s -o /dev/null -w 'BALANCES_%{http_code}\n' --max-time 15 https://api.camxora.com/api/v1/admin/provider-key-balances || true
# confirm openapi path if available
curl -s --max-time 10 https://api.camxora.com/openapi.json 2>/dev/null | python3 -c 'import sys,json; d=json.load(sys.stdin); print("OPENAPI_BALANCES" if "/api/v1/admin/provider-key-balances" in d.get("paths",{}) else "OPENAPI_NO_BALANCES"); print("OPENAPI_FORCE" if any("publish" in p and "installer" in p for p in d.get("paths",{})) else "OPENAPI_CHECK_PUBLISH")' 2>/dev/null || echo OPENAPI_SKIP
# admin static has panel?
grep -l provider-key-balances /opt/camxora/admin/dist/assets/*.js 2>/dev/null | head -3 || grep -l ProviderKeyBalance /var/www/admin*/assets/*.js 2>/dev/null | head -3 || find /opt/camxora -name '*.js' -path '*/admin*' 2>/dev/null | head -5
ls /opt/camxora/admin_portal/dist/assets 2>/dev/null | head -5
ls /var/www/camxora-admin/assets 2>/dev/null | head -5
find /opt/camxora /var/www -maxdepth 4 -type d -name 'assets' 2>/dev/null | head -20
echo VERIFY_DONE
"""
    _, stdout, stderr = client.exec_command(cmd, get_pty=True)
    print(stdout.read().decode("utf-8", errors="replace"))
    err = stderr.read().decode("utf-8", errors="replace")
    if err.strip():
        print(err)
    client.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
