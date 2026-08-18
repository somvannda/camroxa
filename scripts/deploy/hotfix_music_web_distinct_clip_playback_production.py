#!/usr/bin/env python3
"""File-scoped production hotfix: Create clips play distinct audio.

Uploads allowlisted files only. Does not sync a full platform_api tree.
Does not run alembic or rewrite nginx.
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DEPLOY = ROOT / "scripts" / "deploy"
sys.path.insert(0, str(DEPLOY / "venv" / "Lib" / "site-packages"))
sys.path.insert(0, str(DEPLOY / ".venv" / "Lib" / "site-packages"))
sys.path.insert(0, str(DEPLOY))

from deploy import (  # noqa: E402
    ensure_deploy_key,
    load_production_secrets,
    resolve_production_ssh,
    ssh_connect,
)

PRODUCTION_HOST = "82.197.71.248"
FILES = [
    "platform_api/services/audio_origin_proxy.py",
    "platform_api/services/web_music_service.py",
    "platform_api/services/streaming_upload_service.py",
    "music_web/src/components/player-provider.tsx",
    "music_web/src/components/create-page-client.tsx",
]


def _run(client, cmd: str, timeout: int = 480) -> tuple[int, str]:
    _, stdout, stderr = client.exec_command(cmd, get_pty=True, timeout=timeout)
    while not stdout.channel.exit_status_ready():
        time.sleep(0.2)
    out = stdout.read().decode("utf-8", errors="replace")
    err = stderr.read().decode("utf-8", errors="replace")
    code = stdout.channel.recv_exit_status()
    return code, out + ("\n" + err if err.strip() else "")


def main() -> int:
    secrets = load_production_secrets()
    host, user, password = resolve_production_ssh(secrets)
    if host != PRODUCTION_HOST:
        raise SystemExit(f"Refusing non-production host: {host}")
    print(f"Target production host: {host}", flush=True)

    missing = [rel for rel in FILES if not (ROOT / rel).is_file()]
    if missing:
        raise SystemExit(f"Missing source files: {missing}")

    client = ssh_connect(host, user, ensure_deploy_key(), password)
    try:
        sftp = client.open_sftp()
        for rel in FILES:
            remote = f"/opt/camxora/repo/{rel}"
            print(f"Uploading {rel} ...", flush=True)
            sftp.put(str(ROOT / rel), remote)
        sftp.close()

        code, out = _run(
            client,
            r"""
set -e
REPO=/opt/camxora/repo
chown camxora:camxora \
  $REPO/platform_api/services/audio_origin_proxy.py \
  $REPO/platform_api/services/web_music_service.py \
  $REPO/platform_api/services/streaming_upload_service.py \
  $REPO/music_web/src/components/player-provider.tsx \
  $REPO/music_web/src/components/create-page-client.tsx

echo '=== restart api ==='
systemctl restart camxora-api
code=""
for i in 1 2 3 4 5 6 7 8 9 10 11 12 13 14 15 16 17 18 20; do
  code=$(curl -sS -m 3 -o /tmp/prod_health.json -w '%{http_code}' http://127.0.0.1:8100/health || true)
  echo attempt_$i health=$code
  if [ "$code" = "200" ]; then
    break
  fi
  sleep 2
done
echo HEALTH_BODY
cat /tmp/prod_health.json || true
echo
test "$code" = "200"
echo DISTINCT_CLIP_PROD_DONE
""",
            timeout=480,
        )
        print(out.encode("ascii", errors="replace").decode("ascii"))
        print(f"exit={code}", flush=True)
        return code
    finally:
        client.close()


if __name__ == "__main__":
    raise SystemExit(main())
