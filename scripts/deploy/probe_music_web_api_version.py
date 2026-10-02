#!/usr/bin/env python3
"""Probe: what does the DEPLOYED prod music_web actually call? v1 or v3?
Checks built .next bundle, source next.config rewrites, and nginx proxy rules."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DEPLOY = ROOT / "scripts" / "deploy"
sys.path.insert(0, str(DEPLOY / ".venv" / "Lib" / "site-packages"))
sys.path.insert(0, str(DEPLOY))

from deploy import (
    ensure_deploy_key,
    load_production_secrets,
    resolve_production_ssh,
    ssh_connect,
)

PRODUCTION_HOST = "82.197.71.248"

REMOTE_CMD = r"""
set +e
echo '=== [1] prod music_web SOURCE api version calls ==='
grep -rhoE "'/api/v[123]/[a-z0-9/_-]+'" /opt/camxora/repo/music_web/src/lib/*.ts 2>/dev/null | sort | uniq -c | sort -rn | head -15
echo
echo '=== [2] prod music_web next.config rewrites ==='
grep -nE 'rewrites|api|proxy|v1|v3' /opt/camxora/repo/music_web/next.config.ts 2>/dev/null | head -20
echo
echo '=== [3] DEPLOYED .next bundle: which generate URL ==='
grep -rhoE '/api/v[123]/web-music/generate[a-z-]*' /opt/camxora/repo/music_web/.next/static/chunks/*.js 2>/dev/null | sort | uniq -c | head -10
echo
echo '=== [4] nginx proxy rules for /api ==='
grep -rnE 'location|proxy_pass|api/v[123]|api/' /etc/nginx/sites-enabled/ 2>/dev/null | grep -iE 'api|proxy_pass' | head -30
echo '=== [4b] nginx conf.d fallback ==='
grep -rnE 'proxy_pass|location /api' /etc/nginx/conf.d/ 2>/dev/null | head -20
echo 'PROBE2_DONE'
"""


def main() -> int:
    secrets = load_production_secrets()
    host, user, password = resolve_production_ssh(secrets)
    if host != PRODUCTION_HOST:
        raise SystemExit(f"Refusing non-production host: {host}")
    print(f"=== music_web deployed-bundle probe -> {host} ===")
    client = ssh_connect(host, user, ensure_deploy_key(), password)
    try:
        _, stdout, stderr = client.exec_command(REMOTE_CMD, get_pty=False, timeout=120)
        out = stdout.read().decode("utf-8", errors="replace")
        err = stderr.read().decode("utf-8", errors="replace")
        sys.stdout.buffer.write(out.encode("utf-8", errors="replace"))
        if err.strip():
            sys.stderr.write("STDERR: " + err[-1500:] + "\n")
        return 0 if "PROBE2_DONE" in out else 1
    finally:
        client.close()


if __name__ == "__main__":
    raise SystemExit(main())
