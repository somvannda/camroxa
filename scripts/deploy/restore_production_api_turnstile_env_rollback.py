#!/usr/bin/env python3
"""Emergency rollback: remove CLOUDFLARE_TURNSTILE_* from production .env if API cannot start."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from deploy import ensure_deploy_key, load_production_secrets, resolve_production_ssh, ssh_connect

PRODUCTION_HOST = "82.197.71.248"


def main() -> int:
    secrets = load_production_secrets()
    host, user, password = resolve_production_ssh(secrets)
    if host != PRODUCTION_HOST:
        raise SystemExit(f"Refusing non-production host: {host}")

    client = ssh_connect(host, user, ensure_deploy_key(), password)
    remote = r"""
set -e
ENV=/opt/camxora/repo/platform_api/.env
sed -i '/^CLOUDFLARE_TURNSTILE_/d' "$ENV"
systemctl restart camxora-api
sleep 4
systemctl is-active camxora-api
curl -sf -o /dev/null -w 'health=%{http_code}\n' http://127.0.0.1:8100/health || true
echo ROLLBACK_DONE
"""
    _, stdout, stderr = client.exec_command(remote, get_pty=True)
    out = stdout.read().decode("utf-8", errors="replace")
    err = stderr.read().decode("utf-8", errors="replace")
    print(out.encode("utf-8", errors="replace").decode("utf-8", errors="replace"))
    if err.strip():
        print(err.encode("utf-8", errors="replace").decode("utf-8", errors="replace"))
    code = stdout.channel.recv_exit_status()
    client.close()
    return code


if __name__ == "__main__":
    raise SystemExit(main())
