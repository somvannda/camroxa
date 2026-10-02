#!/usr/bin/env python3
"""Prod hotfix v7: fix naive/aware datetime compare in v2 subscription reset.

reset_quota_if_needed used now=datetime.utcnow() (NAIVE) compared against DB
current_period_end/last_credit_reset (AWARE) -> TypeError on EVERY paid-user
subscription refresh ("can't compare offset-naive and offset-aware datetimes").
Free users are unaffected (no subscription row) - this is why pich's paid
account behaves differently. Fix: aware now + timezone import. Backup-first.
"""
from __future__ import annotations

import sys
import time
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
STAMP = time.strftime("%Y%m%d-%H%M%S")

REMOTE_CMD = f"""
set -e
REPO=/opt/camxora/repo/platform_api
cd $REPO
FILE=$REPO/services/v2/subscription_service.py
echo '=== [1] backup ==='
cp -p $FILE $FILE.pre-aware-now-{STAMP}.bak
ls -la $FILE.pre-aware-now-{STAMP}.bak
echo '=== [2] patch (python replace) ==='
env PYTHONPATH=/opt/camxora/repo .venv/bin/python - <<'PYEOF'
from pathlib import Path
f = Path("/opt/camxora/repo/platform_api/services/v2/subscription_service.py")
s = f.read_text()
before = s
s = s.replace("from datetime import datetime, timedelta", "from datetime import datetime, timedelta, timezone", 1)
s = s.replace("        now = datetime.utcnow()", "        now = datetime.now(timezone.utc)", 1)
if s == before:
    raise SystemExit("NO_CHANGE_APPLIED")
f.write_text(s)
print("PATCHED")
PYEOF
echo '=== [3] confirm ==='
grep -n 'timezone' $FILE | head -5
grep -n 'now = datetime.now(timezone.utc)' $FILE
$REPO/.venv/bin/python -m py_compile $FILE && echo COMPILE_OK
echo '=== [4] restart + health ==='
systemctl restart camxora-api
sleep 10
systemctl is-active camxora-api || true
curl -s -o /dev/null -w 'api_health=%{{http_code}}\\n' -m 10 http://127.0.0.1:8100/health || echo API_FAIL
journalctl -u camxora-api --since '2 minutes ago' --no-pager 2>/dev/null | grep -iE 'Traceback|Started server process|ImportError|ModuleNotFoundError' | tail -8 || true
echo FIX_AWARE_NOW_DONE
"""


def main() -> int:
    secrets = load_production_secrets()
    host, user, password = resolve_production_ssh(secrets)
    if host != PRODUCTION_HOST:
        raise SystemExit(f"Refusing non-production host: {host}")
    print(f"=== hotfix v7 (aware datetime) -> production ({host}) ===")
    client = ssh_connect(host, user, ensure_deploy_key(), password)
    try:
        _, stdout, stderr = client.exec_command(REMOTE_CMD, get_pty=False, timeout=200)
        out = stdout.read().decode("utf-8", errors="replace")
        err = stderr.read().decode("utf-8", errors="replace")
        sys.stdout.buffer.write(out.encode("utf-8", errors="replace"))
        if err.strip():
            sys.stderr.write("STDERR: " + err[-2000:] + "\n")
        if "FIX_AWARE_NOW_DONE" not in out or "api_health=200" not in out or "PATCHED" not in out:
            return 1
        return 0
    finally:
        client.close()


if __name__ == "__main__":
    raise SystemExit(main())
