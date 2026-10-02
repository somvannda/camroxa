#!/usr/bin/env python3
"""Check submit_wav_task/poll_wav_status signatures + .env key non-empty."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DEPLOY = ROOT / "scripts" / "deploy"
LOCAL = ROOT / ".dbg" / "live-probe" / "wav_sigs.txt"
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
echo '=== wav methods in suno_client.py ==='
grep -n -A 12 'def submit_wav_task\|def poll_wav_status\|def extract_suno_wav_task_id\|def parse_suno_wav_poll' $REPO/clients/suno_client.py | head -80
echo
echo '=== how do other code paths build client + api_key (web_music_service wav / resolver) ==='
grep -n 'SunoClient(\|api_key=\|def _suno_client_with_pool_key\|KeyEncryption' $REPO/services/suno_audio_resolver.py | head -20
echo
echo '=== .env master key present & non-empty? ==='
grep -cE '^PLATFORM_ENCRYPTION_MASTER_KEY=.+' $REPO/.env || echo EMPTY_OR_MISSING
echo SIGS_DONE
'''


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
            sys.stderr.write("STDERR: " + err[-1200:] + "\n")
        LOCAL.parent.mkdir(parents=True, exist_ok=True)
        LOCAL.write_text(out, encoding="utf-8")
        return 0
    finally:
        client.close()


if __name__ == "__main__":
    raise SystemExit(main())
