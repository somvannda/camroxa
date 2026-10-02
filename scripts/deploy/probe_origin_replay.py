#!/usr/bin/env python3
"""Origin-level replay: are /generate + /generate-styles + /quota reachable?
Also grep error.log strictly for 17:5x window."""
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
echo '=== origin replay: no-auth probes (401/403 expected, 502 = broken) ==='
echo -n 'POST /generate (no auth): '
curl -s -o /dev/null -w '%{http_code}\n' -m 8 -X POST http://127.0.0.1:8100/api/v1/web-music/generate -H 'Content-Type: application/json' -d '{"mode":"advanced","lyrics":"x","title":"t","style":"s","model":"V5_5"}'
echo -n 'POST /generate-styles (no auth): '
curl -s -o /dev/null -w '%{http_code}\n' -m 8 -X POST http://127.0.0.1:8100/api/v1/web-music/generate-styles -H 'Content-Type: application/json' -d '{"style":"s"}'
echo -n 'GET /quota (no auth): '
curl -s -o /dev/null -w '%{http_code}\n' -m 8 http://127.0.0.1:8100/api/v1/web-music/quota
echo -n 'POST /generate-draft (no auth): '
curl -s -o /dev/null -w '%{http_code}\n' -m 8 -X POST http://127.0.0.1:8100/api/v1/web-music/generate-draft -H 'Content-Type: application/json' -d '{"prompt":"x"}'
echo
echo '=== error.log strictly 17:50-17:59 ==='
awk '/2026\/09\/05 17:5[0-9]/' /var/log/nginx/error.log 2>/dev/null | tail -30
echo
echo '=== access.log music 502s in 17:5x with sizes ==='
grep '05/Sep/2026:17:5' /var/log/nginx/access.log 2>/dev/null | grep 'web-music/generate' | tail -10
echo REPLAY_DONE
"""


def main() -> int:
    secrets = load_production_secrets()
    host, user, password = resolve_production_ssh(secrets)
    if host != PRODUCTION_HOST:
        raise SystemExit(f"Refusing non-production host: {host}")
    client = ssh_connect(host, user, ensure_deploy_key(), password)
    try:
        _, stdout, stderr = client.exec_command(REMOTE_CMD, get_pty=False, timeout=120)
        out = stdout.read().decode("utf-8", errors="replace")
        err = stderr.read().decode("utf-8", errors="replace")
        sys.stdout.buffer.write(out.encode("utf-8", errors="replace"))
        if err.strip():
            sys.stderr.write("STDERR: " + err[-1500:] + "\n")
        return 0
    finally:
        client.close()


if __name__ == "__main__":
    raise SystemExit(main())
