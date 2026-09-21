#!/usr/bin/env python3
"""Production hotfix #8: empty host response is inconclusive, never hides a channel.

Host must be 82.197.71.248.
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DEPLOY = ROOT / "scripts" / "deploy"
sys.path.insert(0, str(DEPLOY / ".venv" / "Lib" / "site-packages"))
sys.path.insert(0, str(DEPLOY))

from deploy import (  # noqa: E402
    ensure_deploy_key,
    load_production_secrets,
    resolve_production_ssh,
    ssh_connect,
)

PRODUCTION_HOST = "82.197.71.248"
STAMP = time.strftime("%Y%m%d-%H%M%S")
LOCAL_PATCH = Path(r"C:\Users\KONGSO~1\AppData\Local\Temp\opencode\suno_dl8.patch")

REMOTE_CMD = r'''
set -e
REPO=/opt/camxora/repo
STAMP=''' + STAMP + r'''
echo '=== [1] backup ==='
cp -p $REPO/platform_api/services/batch_service.py $REPO/platform_api/services/batch_service.py.pre-inconcl-$STAMP.bak
echo '=== [2] dry-run ==='
cd $REPO && patch -p1 --binary --dry-run < /tmp/suno_dl8.patch
echo '=== [3] apply ==='
cd $REPO && patch -p1 --binary < /tmp/suno_dl8.patch
echo '=== [4] compile ==='
$REPO/platform_api/.venv/bin/python -m py_compile $REPO/platform_api/services/batch_service.py && echo PYCOMPILE_OK
echo '=== [5] restart + health ==='
systemctl restart camxora-api
for i in 1 2 3 4 5 6; do
  sleep 3
  code=$(curl -s -o /dev/null -w '%{http_code}' -m 5 http://127.0.0.1:8100/health || true)
  echo "health_attempt_$i=$code"
  [ "$code" = "200" ] && break
done
journalctl -u camxora-api --since '2 minutes ago' --no-pager 2>/dev/null \
  | grep -iE 'Traceback|ImportError|ModuleNotFoundError' | tail -8 || true
echo SUNO_INCONCL_DONE
'''


def main() -> int:
    secrets = load_production_secrets()
    host, user, password = resolve_production_ssh(secrets)
    if host != PRODUCTION_HOST:
        raise SystemExit(f"Refusing non-production host: {host}")
    if not LOCAL_PATCH.is_file():
        raise FileNotFoundError(LOCAL_PATCH)
    print(f"=== hotfix probe-inconclusive -> production ({host}) ===")
    client = ssh_connect(host, user, ensure_deploy_key(), password)
    try:
        sftp = client.open_sftp()
        with sftp.file("/tmp/suno_dl8.patch", "wb") as remote_file:
            remote_file.write(LOCAL_PATCH.read_bytes())
        sftp.close()
        _, stdout, stderr = client.exec_command(REMOTE_CMD, get_pty=False, timeout=300)
        out = stdout.read().decode("utf-8", errors="replace")
        err = stderr.read().decode("utf-8", errors="replace")
        sys.stdout.buffer.write(out.encode("utf-8", errors="replace"))
        if err.strip():
            sys.stderr.write("STDERR: " + err[-3000:] + "\n")
        if "SUNO_INCONCL_DONE" not in out or "PYCOMPILE_OK" not in out:
            print("HOTFIX8_INCOMPLETE")
            return 1
        return 0
    finally:
        client.close()


if __name__ == "__main__":
    raise SystemExit(main())
