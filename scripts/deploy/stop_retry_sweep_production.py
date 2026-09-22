#!/usr/bin/env python3
"""Stop the running production retry sweep unit and clear its state row.

Only affects the transient camxora-retry-sweep unit; jobs already retried keep
their DB status. Refuses non-production hosts.
"""
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
echo "--- stop sweep unit ---"
systemctl stop camxora-retry-sweep 2>/dev/null || true
systemctl reset-failed camxora-retry-sweep 2>/dev/null || true
echo "--- clear sweep state row ---"
sudo -u postgres psql -d camxora_platform -t -A -c "DELETE FROM system_settings WHERE key = 'streaming_upload_retry_sweep_v1';"
echo "--- sweep progress so far (jobs retried before stop) ---"
sudo -u postgres psql -d camxora_platform -t -A -c "SELECT 'failed_mp3_now=' || count(*) FROM stream_upload_jobs WHERE status='failed' AND kind IN ('mp3_ok','mp3_alt');"
sudo -u postgres psql -d camxora_platform -t -A -c "SELECT 'success_total=' || count(*) FROM stream_upload_jobs WHERE status='success' AND kind IN ('mp3_ok','mp3_alt');"
echo SWEEP_STOPPED
'''


def main() -> int:
    if "--i-mean-production" not in sys.argv:
        print(
            "Refusing: this stops a PRODUCTION sweep.\n"
            "  python scripts/deploy/stop_retry_sweep_production.py --i-mean-production"
        )
        return 2
    secrets = load_production_secrets()
    host, user, password = resolve_production_ssh(secrets)
    if host != PRODUCTION_HOST:
        raise SystemExit(f"Refusing non-production host: {host}")
    print(f"=== stop sweep on {host} ===")
    client = ssh_connect(host, user, ensure_deploy_key(), password)
    try:
        _, stdout, stderr = client.exec_command(CMD, get_pty=True, timeout=120)
        out = stdout.read().decode("utf-8", errors="replace")
        err = stderr.read().decode("utf-8", errors="replace")
        sys.stdout.buffer.write(out.encode("utf-8", errors="replace") + b"\n")
        if err.strip():
            sys.stderr.write(err[-2000:].encode("utf-8", errors="replace") + b"\n")
        if "SWEEP_STOPPED" not in out:
            return 1
        return stdout.channel.recv_exit_status()
    finally:
        client.close()


if __name__ == "__main__":
    raise SystemExit(main())
