#!/usr/bin/env python3
"""READ-ONLY: poll the running retry sweep (state + success/fail counts)."""
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

PSQL = "sudo -u postgres psql -d camxora_platform -t -A -P pager=off"

CMD = r'''
echo "=== unit ==="
systemctl is-active camxora-retry-sweep 2>/dev/null || true
echo "=== sweep state ==="
%PSQL% -c "SELECT value FROM system_settings WHERE key = 'streaming_upload_retry_sweep_v1';"
echo "=== counters ==="
%PSQL% -c "SELECT 'failed_mp3_now=' || count(*) FILTER (WHERE status='failed' AND kind IN ('mp3_ok','mp3_alt')), 'success_total=' || count(*) FILTER (WHERE status='success' AND kind IN ('mp3_ok','mp3_alt')) FROM stream_upload_jobs;"
echo "=== recent success rate (last hour) ==="
%PSQL% -c "SELECT 'ok_last_hour=' || count(*) FILTER (WHERE status='success' AND created_at > NOW() - interval '1 hour'), 'failed_last_hour=' || count(*) FILTER (WHERE status='failed' AND created_at > NOW() - interval '1 hour') FROM stream_upload_jobs WHERE kind IN ('mp3_ok','mp3_alt');"
echo POLL_DONE
'''


def main() -> int:
    secrets = load_production_secrets()
    host, user, password = resolve_production_ssh(secrets)
    if host != PRODUCTION_HOST:
        raise SystemExit(f"Refusing non-production host: {host}")
    print(f"=== retry sweep poll on {host} ===")
    client = ssh_connect(host, user, ensure_deploy_key(), password)
    try:
        cmd = CMD.replace("%PSQL%", PSQL)
        _, stdout, stderr = client.exec_command(cmd, get_pty=True, timeout=90)
        out = stdout.read().decode("utf-8", errors="replace")
        err = stderr.read().decode("utf-8", errors="replace")
        sys.stdout.buffer.write(out.encode("utf-8", errors="replace") + b"\n")
        if err.strip():
            sys.stderr.write(err[-1500:].encode("utf-8", errors="replace") + b"\n")
        return stdout.channel.recv_exit_status()
    finally:
        client.close()


if __name__ == "__main__":
    raise SystemExit(main())
