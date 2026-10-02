#!/usr/bin/env python3
"""Fetch _upload_web_music_wav method + schedule pattern + constants (prod)."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DEPLOY = ROOT / "scripts" / "deploy"
LOCAL = ROOT / ".dbg" / "live-probe" / "wav_method.txt"
sys.path.insert(0, str(DEPLOY / ".venv" / "Lib" / "site-packages"))
sys.path.insert(0, str(DEPLOY))

from deploy import (
    ensure_deploy_key,
    load_production_secrets,
    resolve_production_ssh,
    ssh_connect,
)

PRODUCTION_HOST = "82.197.71.248"

REMOTE_CMD = r'''
set +e
REPO=/opt/camxora/repo/platform_api
echo '=== def _upload_web_music_wav region (search) ==='
grep -n 'def _upload_web_music_wav\|def schedule_web_music\|def _run_web_music\|_ASSET_WAV_MAX_PER_PASS\|_ASSET_LRC_MAX_PER_PASS\|_ASSET_PASS_TASK_LIMIT\|WEB_MUSIC_B2_BACKFILL_COOLDOWN_S\|_web_music_backfill_inflight\|_web_music_backfill_last' $REPO/services/streaming_upload_service.py | head -30
echo
echo '=== lines 640-1000 (from def area to encrypt) ==='
sed -n '640,1000p' $REPO/services/streaming_upload_service.py
echo WAV_END
'''


def main() -> int:
    secrets = load_production_secrets()
    host, user, password = resolve_production_ssh(secrets)
    if host != PRODUCTION_HOST:
        raise SystemExit(f"Refusing non-production host: {host}")
    client = ssh_connect(host, user, ensure_deploy_key(), password)
    try:
        _, stdout, stderr = client.exec_command(REMOTE_CMD, get_pty=False, timeout=180)
        out = stdout.read().decode("utf-8", errors="replace")
        err = stderr.read().decode("utf-8", errors="replace")
        sys.stdout.buffer.write(out.encode("utf-8", errors="replace"))
        if err.strip():
            sys.stderr.write("STDERR: " + err[-1500:] + "\n")
        LOCAL.parent.mkdir(parents=True, exist_ok=True)
        LOCAL.write_text(out, encoding="utf-8")
        print(f"Saved {LOCAL}")
        return 0
    finally:
        client.close()


if __name__ == "__main__":
    raise SystemExit(main())
