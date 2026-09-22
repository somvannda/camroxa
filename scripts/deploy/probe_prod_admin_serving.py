#!/usr/bin/env python3
"""READ-ONLY: find how prod serves admin.camxora.com (nginx/caddy/docker/systemd)."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DEPLOY = ROOT / "scripts" / "deploy"
sys.path.insert(0, str(DEPLOY / ".venv" / "Lib" / "site-packages"))
sys.path.insert(0, str(DEPLOY))

from deploy import ensure_deploy_key, load_production_secrets, resolve_production_ssh, ssh_connect  # noqa: E402

PRODUCTION_HOST = "82.197.71.248"

CMD = r'''
echo "=== admin_portal dist ==="
ls -la /opt/camxora/repo/admin_portal/dist/ 2>/dev/null | head
ls /opt/camxora/repo/admin_portal/dist/assets/index-*.js 2>/dev/null || echo no-index-js
echo "=== units with admin ==="
systemctl list-units --all --no-pager 2>/dev/null | grep -iE "admin|camxora" || true
echo "=== listeners ==="
ss -ltnp 2>/dev/null | grep -E ':(80|443|3000|3100|8080|8000|9000) ' || true
echo "=== /opt/camxora layout ==="
ls -la /opt/camxora/ 2>/dev/null
echo "=== nginx configs ==="
ls -la /etc/nginx/ 2>/dev/null | head -20
nginx -T 2>/dev/null | grep -nE "server_name|root|proxy_pass|admin" | head -40 || echo no-nginx
echo "=== caddy ==="
which caddy 2>/dev/null && (cat /etc/caddy/Caddyfile 2>/dev/null | head -60 || true) || echo no-caddy
echo "=== openresty / cloudflared ==="
which cloudflared 2>/dev/null || echo no-cloudflared
echo PROBE_DONE
'''


def main() -> int:
    secrets = load_production_secrets()
    host, user, password = resolve_production_ssh(secrets)
    if host != PRODUCTION_HOST:
        raise SystemExit(f"Refusing non-production host: {host}")
    print(f"=== admin serving probe on {host} ===")
    client = ssh_connect(host, user, ensure_deploy_key(), password)
    try:
        _, stdout, stderr = client.exec_command(CMD, get_pty=True, timeout=90)
        out = stdout.read().decode("utf-8", errors="replace")
        err = stderr.read().decode("utf-8", errors="replace")
        sys.stdout.buffer.write(out.encode("utf-8", errors="replace") + b"\n")
        if err.strip():
            sys.stderr.write(err[-2000:].encode("utf-8", errors="replace") + b"\n")
        return stdout.channel.recv_exit_status()
    finally:
        client.close()


if __name__ == "__main__":
    raise SystemExit(main())
