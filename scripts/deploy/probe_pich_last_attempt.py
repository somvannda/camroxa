#!/usr/bin/env python3
"""Grep prod journal for pich's latest attempt + check what the frontend fires on Create."""
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
echo '=== [1] api journal: pich + web-music markers (last 45 min) ==='
journalctl -u camxora-api --since "45 minutes ago" --no-pager 2>/dev/null | grep -iE '5b1673dc|web-music /generate|service\.generate|text-assist LLM failed|AI assist|ExternalServiceError|generate-styles|generate-draft|Traceback|title cannot exceed' | tail -60
echo
echo '=== [2] music_web journal (last 45 min): proxied errors ==='
journalctl -u camxora-music --since "45 minutes ago" --no-pager 2>/dev/null | grep -iE '5b1673dc|502|503|504|generate|assist|error' | tail -40
echo
echo '=== [3] what does prod music_web Create click call? (source) ==='
grep -rnoE 'generate-styles|generate-draft|/api/v1/web-music/generate[^)]*|submitSong|createSong|generate_styles|autoGenerateStyle' /opt/camxora/repo/music_web/src/app /opt/camxora/repo/music_web/src/components /opt/camxora/repo/music_web/src/lib 2>/dev/null | head -40
echo JOURNAL_PROBE_DONE
"""


def main() -> int:
    secrets = load_production_secrets()
    host, user, password = resolve_production_ssh(secrets)
    if host != PRODUCTION_HOST:
        raise SystemExit(f"Refusing non-production host: {host}")
    print(f"=== journal + frontend probe -> {host} ===")
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
