#!/usr/bin/env python3
"""nginx access/error logs: what status did the browser get for web-music/generate?"""
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
echo '=== nginx access log dir ==='
ls -la /var/log/nginx/ 2>/dev/null | head -15
echo
echo '=== recent web-music/generate requests in access logs (last 2h) ==='
for f in /var/log/nginx/access.log /var/log/nginx/*.log; do
  [ -f "$f" ] || continue
  echo "--- $f ---"
  tail -n 20000 "$f" 2>/dev/null | grep -E 'web-music/(generate|quota)' | grep -E "$(date -d '2 hours ago' '+%d/%b/%Y:%H')|$(date '+%d/%b/%Y:%H')" | tail -25
done
echo
echo '=== nginx error log tail ==='
for f in /var/log/nginx/error.log; do
  [ -f "$f" ] || continue
  tail -n 60 "$f" 2>/dev/null | tail -30
done
echo NGINX_PROBE_DONE
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
