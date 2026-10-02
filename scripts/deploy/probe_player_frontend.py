#!/usr/bin/env python3
"""How does prod music_web frontend play packaged (pkg ready) clips?"""
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
MW=/opt/camxora/repo/music_web/src
echo '=== refs to encrypted_playback_required / package_status / hls ==='
grep -rn 'encrypted_playback_required\|package_status\|licenses/hls\|hls.js\|hls\.js\|licenses/segments\|licenses/play' $MW 2>/dev/null | grep -v '.bak' | head -40
echo
echo '=== player components ==='
grep -rln 'audio_url\|playTrack\|<audio\|hls' $MW --include=*.tsx --include=*.ts 2>/dev/null | grep -v '.bak' | head -20
echo PLAYER_PROBE_DONE
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
            sys.stderr.write("STDERR: " + err[-1500:] + "\n")
        return 0
    finally:
        client.close()


if __name__ == "__main__":
    raise SystemExit(main())
