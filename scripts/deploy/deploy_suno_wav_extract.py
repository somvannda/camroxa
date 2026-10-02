#!/usr/bin/env python3
"""Deploy v12b: module-level wav helper calls in streaming_upload_service."""
from __future__ import annotations

import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DEPLOY = ROOT / "scripts" / "deploy"
LOCAL_PATCH = ROOT / ".dbg" / "live-probe" / "patch_suno_wav_extract.py"
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
REMOTE_PATCH = "/tmp/patch_suno_wav_extract.py"

REMOTE_CMD = f"""
set -e
REPO=/opt/camxora/repo/platform_api
echo '=== [1] backup ==='
cp -p $REPO/services/streaming_upload_service.py $REPO/services/streaming_upload_service.py.pre-wavextract-{STAMP}.bak
ls -la $REPO/services/streaming_upload_service.py.pre-wavextract-{STAMP}.bak
echo '=== [2] apply ==='
cd $REPO && .venv/bin/python /tmp/patch_suno_wav_extract.py
echo '=== [3] compile + markers ==='
$REPO/.venv/bin/python -m py_compile $REPO/services/streaming_upload_service.py && echo SUS_OK
grep -n 'extract_suno_wav_task_id(result)' $REPO/services/streaming_upload_service.py | head -1
grep -n 'parse_suno_wav_poll(result)' $REPO/services/streaming_upload_service.py | head -1
echo '=== [4] restart + health ==='
systemctl restart camxora-api
sleep 10
systemctl is-active camxora-api || true
curl -s -o /dev/null -w 'api_health=%{{http_code}}\\n' -m 10 http://127.0.0.1:8100/health || echo API_FAIL
journalctl -u camxora-api --since '2 minutes ago' --no-pager 2>/dev/null | grep -iE 'Traceback|Started server process|ImportError|ModuleNotFoundError' | tail -8 || true
echo SUNO_WAVEXTRACT_DONE
"""


def main() -> int:
    secrets = load_production_secrets()
    host, user, password = resolve_production_ssh(secrets)
    if host != PRODUCTION_HOST:
        raise SystemExit(f"Refusing non-production host: {host}")
    if not LOCAL_PATCH.is_file():
        raise FileNotFoundError(LOCAL_PATCH)
    print(f"=== hotfix v12b (wav module helpers) -> production ({host}) ===")
    client = ssh_connect(host, user, ensure_deploy_key(), password)
    try:
        sftp = client.open_sftp()
        with sftp.file(REMOTE_PATCH, "wb") as rf:
            rf.write(LOCAL_PATCH.read_bytes())
        sftp.close()

        _, stdout, stderr = client.exec_command(REMOTE_CMD, get_pty=False, timeout=240)
        out = stdout.read().decode("utf-8", errors="replace")
        err = stderr.read().decode("utf-8", errors="replace")
        sys.stdout.buffer.write(out.encode("utf-8", errors="replace"))
        if err.strip():
            sys.stderr.write("STDERR: " + err[-2000:] + "\n")
        if "SUNO_WAVEXTRACT_DONE" not in out or "api_health=200" not in out or "ALL_PATCHES_OK" not in out:
            return 1
        return 0
    finally:
        client.close()


if __name__ == "__main__":
    raise SystemExit(main())
