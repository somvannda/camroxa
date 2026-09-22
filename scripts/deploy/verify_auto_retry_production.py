#!/usr/bin/env python3
"""READ-ONLY: verify prod auto-retry loop start + pass logs + sweep state."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DEPLOY = ROOT / "scripts" / "deploy"
sys.path.insert(0, str(DEPLOY / ".venv" / "Lib" / "site-packages"))
sys.path.insert(0, str(DEPLOY))

from deploy import ensure_deploy_key, load_production_secrets, resolve_production_ssh, ssh_connect  # noqa: E402

PRODUCTION_HOST = "82.197.71.248"

CMD = r'''
echo "=== api startup markers (exact) ==="
journalctl -u camxora-api --since "10 minutes ago" --no-pager 2>/dev/null | grep -iE "Streaming upload auto-retry loop started|Streaming upload auto-retry loop not started|Streaming upload auto-retry is disabled" || echo NO_MARKER
echo "=== all auto-retry mentions (last 10 min) ==="
journalctl -u camxora-api --since "10 minutes ago" --no-pager 2>/dev/null | grep -iE "auto-retry|Auto-retry" || echo NO_AUTORETRY_LINES
echo "=== application startup complete count ==="
journalctl -u camxora-api --since "10 minutes ago" --no-pager 2>/dev/null | grep -cE "Application startup complete" || true
echo "=== manual sweep still running? ==="
sudo -u postgres psql -d camxora_platform -t -A -c "SELECT value FROM system_settings WHERE key='streaming_upload_retry_sweep_v1';"
sudo -u postgres psql -d camxora_platform -t -A -c "SELECT 'failed_mp3_now=' || count(*) FROM stream_upload_jobs WHERE status='failed' AND kind IN ('mp3_ok','mp3_alt');"
echo VERIFY_DONE
'''


def main() -> int:
    secrets = load_production_secrets()
    host, user, password = resolve_production_ssh(secrets)
    if host != PRODUCTION_HOST:
        raise SystemExit(f"Refusing non-production host: {host}")
    print(f"=== auto-retry verify on {host} ===")
    client = ssh_connect(host, user, ensure_deploy_key(), password)
    try:
        _, stdout, stderr = client.exec_command(CMD, get_pty=True, timeout=120)
        out = stdout.read().decode("utf-8", errors="replace")
        err = stderr.read().decode("utf-8", errors="replace")
        print(out)
        if err.strip():
            print("STDERR:", err[-1500:])
        return stdout.channel.recv_exit_status()
    finally:
        client.close()


if __name__ == "__main__":
    raise SystemExit(main())
