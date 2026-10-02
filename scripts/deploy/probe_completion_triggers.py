#!/usr/bin/env python3
"""Trace what the worker schedules on web_music completion (b2/wav/lrc/package)."""
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

REMOTE_CMD = r'''
set +e
REPO=/opt/camxora/repo/platform_api
echo '=== [1] callers of the schedule functions ==='
grep -rn 'schedule_suno_streaming_upload\|schedule_web_music_b2_backfill\|schedule_web_music_lrc_upload\|schedule_.*wav\|schedule_suno_wav\|schedule_package' $REPO --include=*.py 2>/dev/null | grep -v '.bak' | head -30
echo
echo '=== [2] where wav_status is set / wav job scheduled ==='
grep -rn 'wav_status\s*=\|wav_status="pending"\|JOB_WEB_MUSIC_WAV\|job_type.*wav\|WAV_CONVERT\|convert_wav\|schedule_wav' $REPO --include=*.py 2>/dev/null | grep -v '.bak' | head -30
echo
echo '=== [3] completion/finalize for web music in generation_service ==='
grep -n 'def .*finalize\|def .*complete\|def .*web_music\|schedule\|package' $REPO/services/generation_service.py 2>/dev/null | grep -iE 'def |package|upload|wav|lrc' | head -30
echo
echo '=== [4] job types constants ==='
grep -rn 'JOB_WEB_MUSIC\|JOB_SUNO\|JOB_.*WAV\|JOB_.*LRC\|PRI_WEB_MUSIC' $REPO/services/job_types.py 2>/dev/null | head -30
echo TRIGGER_DONE
'''


def main() -> int:
    secrets = load_production_secrets()
    host, user, password = resolve_production_ssh(secrets)
    if host != PRODUCTION_HOST:
        raise SystemExit(f"Refusing non-production host: {host}")
    client = ssh_connect(host, user, ensure_deploy_key(), password)
    try:
        _, stdout, stderr = client.exec_command(REMOTE_CMD, get_pty=False, timeout=150)
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
