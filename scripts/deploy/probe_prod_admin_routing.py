#!/usr/bin/env python3
"""READ-ONLY: inspect prod API prefix config + nginx routing for admin portal."""
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
echo "=== config.py prefix defaults ==="
grep -nE "api_v1_prefix|api_v3_prefix|api_v[0-9]_prefix" /opt/camxora/repo/platform_api/config.py 2>/dev/null | head -20 || echo none
echo "=== .env prefix overrides ==="
grep -nE "API_V1_PREFIX|API_V3_PREFIX|api_v1_prefix|api_v3_prefix" /opt/camxora/repo/platform_api/.env 2>/dev/null | sed -E 's/(=.*)/=<redacted>/' || echo none
echo "=== main.py mounts (v3) ==="
grep -nE "api_v3_prefix|api_v3|/api/v3" /opt/camxora/repo/platform_api/main.py | head -20 || echo none
echo "=== nginx: admin api location ==="
grep -rnE "location.*api|proxy_pass|admin" /etc/nginx/sites-enabled/ /etc/nginx/conf.d/ 2>/dev/null | grep -iE "api|admin" | head -30 || echo none
echo PROBE_DONE
'''


def main() -> int:
    secrets = load_production_secrets()
    host, user, password = resolve_production_ssh(secrets)
    if host != PRODUCTION_HOST:
        raise SystemExit(f"Refusing non-production host: {host}")
    print(f"=== prod prefix/nginx probe on {host} ===")
    client = ssh_connect(host, user, ensure_deploy_key(), password)
    try:
        _, stdout, stderr = client.exec_command(CMD, get_pty=True, timeout=60)
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
