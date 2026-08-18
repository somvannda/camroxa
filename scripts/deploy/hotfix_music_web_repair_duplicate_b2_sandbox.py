#!/usr/bin/env python3
"""Sandbox hotfix: re-upload duplicate web-music ok/alt B2 objects."""

from __future__ import annotations

import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DEPLOY = ROOT / "scripts" / "deploy"
sys.path.insert(0, str(DEPLOY / "venv" / "Lib" / "site-packages"))
sys.path.insert(0, str(DEPLOY / ".venv" / "Lib" / "site-packages"))
sys.path.insert(0, str(DEPLOY))

from deploy import ensure_deploy_key, load_sandbox_secrets, resolve_sandbox_ssh, ssh_connect  # noqa: E402

SANDBOX_HOST = "46.250.235.83"
FILES = [
    "platform_api/services/storage_service.py",
    "platform_api/services/web_music_service.py",
    "platform_api/services/streaming_upload_service.py",
    "platform_api/services/suno_audio_resolver.py",
]


def main() -> int:
    secrets = load_sandbox_secrets()
    host, user, password = resolve_sandbox_ssh(secrets)
    if host != SANDBOX_HOST:
        raise SystemExit(f"Refusing non-sandbox host: {host}")
    print(f"Target sandbox host: {host}", flush=True)
    missing = [rel for rel in FILES if not (ROOT / rel).is_file()]
    if missing:
        raise SystemExit(f"Missing source files: {missing}")
    repair_py = DEPLOY / "_remote_repair_duplicate_b2.py"
    client = ssh_connect(host, user, ensure_deploy_key(), password)
    try:
        sftp = client.open_sftp()
        for rel in FILES:
            print(f"Uploading {rel} ...", flush=True)
            sftp.put(str(ROOT / rel), f"/opt/camxora/repo/{rel}")
        sftp.put(str(repair_py), "/tmp/repair_duplicate_b2.py")
        sftp.close()
        cmd = r"""
set -e
REPO=/opt/camxora/repo
chown camxora:camxora \
  $REPO/platform_api/services/storage_service.py \
  $REPO/platform_api/services/web_music_service.py \
  $REPO/platform_api/services/streaming_upload_service.py \
  $REPO/platform_api/services/suno_audio_resolver.py
systemctl restart camxora-api
code=""
for i in 1 2 3 4 5 6 7 8 9 10 11 12 13 14 15 16 17 18 20; do
  code=$(curl -sS -m 3 -o /dev/null -w '%{http_code}' http://127.0.0.1:8100/health || true)
  echo attempt_$i health=$code
  if [ "$code" = "200" ]; then
    break
  fi
  sleep 2
done
test "$code" = "200"
echo '=== repair duplicate b2 clips ==='
sudo -u camxora bash -lc 'set -a && source /opt/camxora/repo/platform_api/.env && set +a && PYTHONPATH=/opt/camxora/repo /opt/camxora/repo/platform_api/.venv/bin/python /tmp/repair_duplicate_b2.py'
echo DUPLICATE_B2_SANDBOX_DONE
"""
        _, stdout, _stderr = client.exec_command(cmd, get_pty=True, timeout=600)
        while not stdout.channel.exit_status_ready():
            time.sleep(0.2)
        out = stdout.read().decode("utf-8", errors="replace")
        code = stdout.channel.recv_exit_status()
        print(out.encode("ascii", errors="replace").decode("ascii"))
        print(f"exit={code}", flush=True)
        return code
    finally:
        client.close()


if __name__ == "__main__":
    raise SystemExit(main())
