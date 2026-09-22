#!/usr/bin/env python3
"""Start the production failed-mp3 retry-all sweep (detached, camxora user).

Uploads _retry_sweep_starter.py, launches it via a transient systemd unit so it
survives this SSH session, then polls DB progress for ~60s and reports.
Refuses non-production hosts.

Usage: python scripts/deploy/run_retry_sweep_production.py
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DEPLOY = ROOT / "scripts" / "deploy"
sys.path.insert(0, str(DEPLOY / ".venv" / "Lib" / "site-packages"))
sys.path.insert(0, str(DEPLOY))

from deploy import ensure_deploy_key, load_production_secrets, resolve_production_ssh, ssh_connect  # noqa: E402

PRODUCTION_HOST = "82.197.71.248"
STARTER = DEPLOY / "_retry_sweep_starter.py"

REMOTE_CMD = r'''
set -e
echo "--- 1. stop stale unit if any ---"
systemctl stop camxora-retry-sweep 2>/dev/null || true
systemctl reset-failed camxora-retry-sweep 2>/dev/null || true
# We are the only operator; the prior unit (if any) is now dead, so clear its
# sweep row so the fresh claim below is clean.
sudo -u postgres psql -d camxora_platform -t -A -c "DELETE FROM system_settings WHERE key = 'streaming_upload_retry_sweep_v1';" || true
echo "--- 2. discover camxora-api EnvironmentFile ---"
ENVFILE=$(systemctl cat camxora-api 2>/dev/null | sed -n 's/^EnvironmentFile=//p' | head -1)
echo "ENVFILE=$ENVFILE"
if [ -z "$ENVFILE" ]; then echo NO_ENVFILE; exit 1; fi
echo "--- 3. start sweep unit (same env as camxora-api) ---"
systemd-run --unit=camxora-retry-sweep --collect \
  -p User=camxora \
  -p WorkingDirectory=/opt/camxora/repo \
  -p EnvironmentFile="$ENVFILE" \
  -p Environment=PYTHONPATH=/opt/camxora/repo \
  /opt/camxora/repo/platform_api/.venv/bin/python /tmp/retry_sweep_starter.py
sleep 8
systemctl is-active camxora-retry-sweep || true
echo "--- 4. early unit log ---"
journalctl -u camxora-retry-sweep --no-pager -n 15 2>/dev/null | tail -15 || true
echo "--- 5. DB sweep state + progress after 30s ---"
sleep 22
sudo -u postgres psql -d camxora_platform -t -A -c "SELECT value FROM system_settings WHERE key = 'streaming_upload_retry_sweep_v1';"
echo "--- 6. current failed mp3 total ---"
sudo -u postgres psql -d camxora_platform -t -A -c "SELECT 'failed_mp3_now=' || count(*) FROM stream_upload_jobs WHERE status='failed' AND kind IN ('mp3_ok','mp3_alt');"
echo RUN_RETRY_SWEEP_DONE
'''


def main() -> int:
    if "--i-mean-production" not in sys.argv:
        print(
            "Refusing: this starts a sweep over PRODUCTION upload jobs.\n"
            "  python scripts/deploy/run_retry_sweep_production.py --i-mean-production"
        )
        return 2
    secrets = load_production_secrets()
    host, user, password = resolve_production_ssh(secrets)
    if host != PRODUCTION_HOST:
        raise SystemExit(f"Refusing non-production host: {host}")
    print(f"=== start failed-mp3 retry sweep on {host} ===")
    client = ssh_connect(host, user, ensure_deploy_key(), password)
    try:
        sftp = client.open_sftp()
        with sftp.file("/tmp/retry_sweep_starter.py", "wb") as remote_file:
            remote_file.write(STARTER.read_bytes().replace(b"\r\n", b"\n"))
        sftp.close()
        print("Uploaded starter -> /tmp/retry_sweep_starter.py")
        _, stdout, stderr = client.exec_command(REMOTE_CMD, get_pty=True, timeout=240)
        out = stdout.read().decode("utf-8", errors="replace")
        err = stderr.read().decode("utf-8", errors="replace")
        sys.stdout.buffer.write(out.encode("utf-8", errors="replace") + b"\n")
        if err.strip():
            sys.stderr.write(err[-2500:].encode("utf-8", errors="replace") + b"\n")
        if "RUN_RETRY_SWEEP_DONE" not in out:
            print("\nSweep start did not finish cleanly.")
            return 1
        return stdout.channel.recv_exit_status()
    finally:
        client.close()


if __name__ == "__main__":
    raise SystemExit(main())
