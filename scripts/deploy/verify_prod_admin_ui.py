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
set -e
DIST=/opt/camxora/repo/admin_portal/dist
# also check nginx root
NGINX=$(grep -R 'root ' /etc/nginx/sites-enabled/* 2>/dev/null | grep -i admin | head -5 || true)
echo "NGINX_HINTS:"
echo "$NGINX"
for d in "$DIST" /var/www/camxora-admin /var/www/admin /opt/camxora/admin; do
  if [ -d "$d/assets" ]; then
    echo "CHECK_DIR $d"
    if grep -Rql 'provider-key-balances\|ProviderKeyBalance\|providerKeyBalances' "$d/assets" 2>/dev/null; then
      echo "ADMIN_UI_BALANCES_OK $d"
    else
      echo "ADMIN_UI_BALANCES_MISSING $d"
    fi
    if grep -Rql 'Force update\|forceUpdate\|force_update' "$d/assets" 2>/dev/null; then
      echo "ADMIN_UI_FORCE_OK $d"
    else
      echo "ADMIN_UI_FORCE_MISSING $d"
    fi
  fi
done
echo UI_CHECK_DONE
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
