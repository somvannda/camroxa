#!/usr/bin/env python3
"""Production: file-scoped deploy of the MP3 Xing/Info duration-header fix.

Uploads only the four changed platform_api files (never a full tree sync), backs
up the existing files, py_compiles and import dry-runs them, and only restarts
camxora-api/workers if the dry-run passes. On import failure it restores the
backups and leaves the API untouched. Refuses non-production hosts.

Dry-run by default. Pass --apply to upload + restart.
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
    CANONICAL_PRODUCTION_HOST,
    CANONICAL_SANDBOX_HOST,
    ensure_deploy_key,
    load_production_secrets,
    resolve_production_ssh,
    ssh_connect,
)

PRODUCTION_HOST = "82.197.71.248"
STAMP = time.strftime("%Y%m%d-%H%M%S")

FILES = (
    "platform_api/services/mp3_duration_header.py",
    "platform_api/services/streaming_upload_service.py",
    "platform_api/services/web_music_service.py",
    "platform_api/routers/admin_user_web_music.py",
)
# Existing files get a timestamped backup; the new module does not.
BACKUP_FILES = (
    "platform_api/services/streaming_upload_service.py",
    "platform_api/services/web_music_service.py",
    "platform_api/routers/admin_user_web_music.py",
)

REMOTE_CMD = r'''
set -e
API=/opt/camxora/repo/platform_api
STAMP="%STAMP%"

echo "--- 1. backup ---"
for f in services/streaming_upload_service.py services/web_music_service.py routers/admin_user_web_music.py; do
  cp -p "$API/$f" "$API/$f.pre-mp3xing-$STAMP.bak"
done

echo "--- 2. chown ---"
chown camxora:camxora \
  "$API/services/mp3_duration_header.py" \
  "$API/services/streaming_upload_service.py" \
  "$API/services/web_music_service.py" \
  "$API/routers/admin_user_web_music.py"

echo "--- 3. py_compile ---"
sudo -u camxora bash -lc "cd $API && .venv/bin/python -m py_compile \
  services/mp3_duration_header.py services/streaming_upload_service.py \
  services/web_music_service.py routers/admin_user_web_music.py"
echo COMPILE_OK

echo "--- 4. import dry-run ---"
if ! sudo -u camxora env PYTHONPATH=/opt/camxora/repo "$API/.venv/bin/python" -c \
  "import platform_api.services.mp3_duration_header, platform_api.services.streaming_upload_service, platform_api.services.web_music_service, platform_api.routers.admin_user_web_music; print('IMPORT_OK')"; then
  echo "IMPORT_FAILED - restoring backups"
  for f in services/streaming_upload_service.py services/web_music_service.py routers/admin_user_web_music.py; do
    cp -p "$API/$f.pre-mp3xing-$STAMP.bak" "$API/$f"
  done
  rm -f "$API/services/mp3_duration_header.py"
  chown camxora:camxora "$API/services/streaming_upload_service.py" "$API/services/web_music_service.py" "$API/routers/admin_user_web_music.py"
  echo RESTORED
  exit 1
fi

echo "--- 5. ffmpeg ---"
which ffmpeg >/dev/null 2>&1 && echo HAS_FFMPEG || echo NO_FFMPEG

echo "--- 6. restart camxora-api + workers ---"
systemctl restart camxora-api
for unit in camxora-worker-draft@1 camxora-worker-draft@2 camxora-worker-draft@3 camxora-worker-draft@4 camxora-worker-suno@1 camxora-worker-suno@2 camxora-worker-images@1 camxora-worker-images@2; do
  systemctl restart "$unit" || true
done
sleep 6
systemctl is-active camxora-api
curl -s -o /dev/null -w "api_health=%{http_code}\n" -m 8 http://127.0.0.1:8100/health || echo API_FAIL
journalctl -u camxora-api --since "1 minute ago" --no-pager 2>/dev/null | grep -iE "Traceback|ImportError|Application startup|Started server" | tail -5 || true
echo MP3XING_DEPLOY_DONE
'''


def main() -> int:
    apply = "--apply" in sys.argv
    secrets = load_production_secrets()
    host, user, password = resolve_production_ssh(secrets)
    if host != CANONICAL_PRODUCTION_HOST or host == CANONICAL_SANDBOX_HOST:
        raise SystemExit(f"Refusing non-production host: {host}")
    print(f"=== MP3 duration-header prod deploy [{'APPLY' if apply else 'DRY-RUN'}] {host} ===")

    client = ssh_connect(host, user, ensure_deploy_key(), password)
    try:
        if not apply:
            _, out, _ = client.exec_command(
                "cd /opt/camxora/repo && "
                "test -f platform_api/services/mp3_duration_header.py && echo REMOTE_HAS_MODULE || echo REMOTE_NO_MODULE; "
                "which ffmpeg >/dev/null 2>&1 && echo HAS_FFMPEG || echo NO_FFMPEG",
                timeout=60,
            )
            print(out.read().decode("utf-8", errors="replace"))
            print("DRY-RUN only; pass --apply to upload + restart.")
            return 0

        sftp = client.open_sftp()
        for rel in FILES:
            remote = f"/opt/camxora/repo/{rel}"
            print(f"Uploading {rel}")
            sftp.put(str(ROOT / rel), remote)
        sftp.close()

        _, stdout, stderr = client.exec_command(
            REMOTE_CMD.replace("%STAMP%", STAMP), get_pty=False, timeout=300
        )
        o = stdout.read().decode("utf-8", errors="replace")
        e = stderr.read().decode("utf-8", errors="replace")
        sys.stdout.buffer.write(o.encode("utf-8", errors="replace"))
        if e.strip():
            sys.stderr.write(e[-3000:] + "\n")
        if "IMPORT_OK" not in o:
            print("\nImport dry-run FAILED - API was NOT restarted. Backups restored.")
            return 1
        if "MP3XING_DEPLOY_DONE" not in o:
            print("\nDeploy did not finish cleanly.")
            return 1
        return 0
    finally:
        client.close()


if __name__ == "__main__":
    raise SystemExit(main())
