#!/usr/bin/env python3
"""Where does 'AI assist is temporarily unavailable' live in prod music_web src?
And what does the Create submit flow call first?"""
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
echo '=== [1] exact phrase locations ==='
grep -rn 'AI assist is temporarily unavailable\|temporarily unavailable' $MW 2>/dev/null | head -30
echo
echo '=== [2] files calling generate-styles / generate-draft / generate ==='
grep -rln 'generate-styles\|generate-draft\|web-music/generate' $MW 2>/dev/null | head -20
echo
echo '=== [3] create submit flow files (components/pages) ==='
grep -rln 'generate-styles\|generateStyles\|generate-styles(' $MW --include=*.tsx --include=*.ts 2>/dev/null | grep -viE 'web-music-api' | head -15
echo
echo '=== [4] build timestamp of deployed music_web ==='
ls -la /opt/camxora/repo/music_web/.next/BUILD_ID 2>/dev/null
stat -c '%y %n' /opt/camxora/repo/music_web/src/lib/web-music-api.ts 2>/dev/null
echo SRC_PROBE_DONE
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
            sys.stderr.write("STDERR: " + err[-1500:] + "\n")
        return 0
    finally:
        client.close()


if __name__ == "__main__":
    raise SystemExit(main())
