#!/usr/bin/env python3
"""Inspect camxora-api env source + current asset-recovery env knobs (READ-ONLY)."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DEPLOY = ROOT / "scripts" / "deploy"
sys.path.insert(0, str(DEPLOY / ".venv" / "Lib" / "site-packages"))
sys.path.insert(0, str(DEPLOY))

from deploy import ensure_deploy_key, load_production_secrets, resolve_production_ssh, ssh_connect  # noqa: E402

PRODUCTION_HOST = "82.197.71.248"

REMOTE_CMD = r"""
set +e
REPO=/opt/camxora/repo/platform_api
echo '=== systemd unit env config ==='
systemctl cat camxora-api | grep -iE 'Environment|ExecStart' | head -10
echo
echo '=== env files present ==='
ls -la $REPO/.env 2>/dev/null
ls -la /opt/camxora/.env 2>/dev/null
echo
echo '=== current knobs in service file ==='
grep -n '_ASSET_WAV_MAX_PER_PASS\|_ASSET_LRC_MAX_PER_PASS\|_ASSET_PASS_TASK_LIMIT\|WEB_MUSIC_ASSET_WAV_MAX_PER_PASS\|WEB_MUSIC_ASSET_LRC_MAX_PER_PASS\|WEB_MUSIC_ASSET_PASS_TASK_LIMIT' $REPO/services/streaming_upload_service.py | head -8
echo
echo '=== knob env vars already set in .env? ==='
grep -nE 'WEB_MUSIC_ASSET_(WAV|LRC|PASS)' $REPO/.env 2>/dev/null || echo NONE_SET
echo INSPECT_DONE
"""


def main() -> int:
    secrets = load_production_secrets()
    host, user, password = resolve_production_ssh(secrets)
    if host != PRODUCTION_HOST:
        raise SystemExit(f"Refusing non-production host: {host}")
    client = ssh_connect(host, user, ensure_deploy_key(), password)
    try:
        _, stdout, stderr = client.exec_command(REMOTE_CMD, get_pty=False, timeout=90)
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
