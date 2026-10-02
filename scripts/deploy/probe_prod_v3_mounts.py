#!/usr/bin/env python3
"""Probe: what API version prefixes does prod camxora-api serve, and is the
credits-only v3 cutover flag live on prod?"""
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
REPO=/opt/camxora/repo/platform_api
echo '=== [1] prod main.py version-prefix mounts ==='
grep -nE 'api_v1_prefix|api_v2_prefix|api_v3_prefix|include_router\(router, prefix|_mount\(' $REPO/main.py | head -40
echo
echo '=== [2] prod config credits_only_v3_charge default ==='
grep -nE 'credits_only_v3_charge|credits_only' $REPO/config.py | head -10
echo
echo '=== [3] openapi path counts per version prefix ==='
curl -s -m 8 http://127.0.0.1:8100/api/v1/openapi.json 2>/dev/null | grep -oE '"/api/v[123]/' | sort | uniq -c | sort -rn | head -10
curl -s -m 8 http://127.0.0.1:8100/api/v3/openapi.json 2>/dev/null | grep -oE '"/api/v[123]/' | sort | uniq -c | sort -rn | head -10
echo
echo '=== [4] live probe: /api/v3 vs /api/v1 web-music quota (401 = route exists, 404 = no route) ==='
curl -s -o /dev/null -w 'v3_quota=%{http_code}\n' -m 8 http://127.0.0.1:8100/api/v3/web-music/quota
curl -s -o /dev/null -w 'v1_quota=%{http_code}\n' -m 8 http://127.0.0.1:8100/api/v1/web-music/quota
echo 'PROBE_DONE'
"""


def main() -> int:
    secrets = load_production_secrets()
    host, user, password = resolve_production_ssh(secrets)
    if host != PRODUCTION_HOST:
        raise SystemExit(f"Refusing non-production host: {host}")
    print(f"=== prod v3/v1 mount probe -> {host} ===")
    client = ssh_connect(host, user, ensure_deploy_key(), password)
    try:
        _, stdout, stderr = client.exec_command(REMOTE_CMD, get_pty=False, timeout=120)
        out = stdout.read().decode("utf-8", errors="replace")
        err = stderr.read().decode("utf-8", errors="replace")
        sys.stdout.buffer.write(out.encode("utf-8", errors="replace"))
        if err.strip():
            sys.stderr.write("STDERR: " + err[-1000:] + "\n")
        return 0 if "PROBE_DONE" in out else 1
    finally:
        client.close()


if __name__ == "__main__":
    raise SystemExit(main())
