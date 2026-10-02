#!/usr/bin/env python3
"""Dump prod music_web /generate payload construction (api fn + caller)."""
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

REMOTE_CMD = r"""
set +e
MW=/opt/camxora/repo/music_web/src
echo '=== web-music-api.ts generate fn (lines 150-215) ==='
sed -n '150,215p' $MW/lib/web-music-api.ts
echo
echo '=== who calls generateSong / the submit: field names in create flow ==='
grep -rn 'mode\b\|model:\|vocal\|generateSong\|submitGenerate\|WebMusicGenerateInput\|generate(' $MW/app $MW/components $MW/lib 2>/dev/null | grep -viE 'web-music-api.ts|\.bak|generate-draft|generate-styles' | head -50
echo
echo '=== type WebMusicGenerateInput ==='
grep -rn 'WebMusicGenerateInput' $MW/lib $MW/types 2>/dev/null | head -10
echo PAYLOAD_PROBE_DONE
"""


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
        return 0
    finally:
        client.close()


if __name__ == "__main__":
    raise SystemExit(main())
