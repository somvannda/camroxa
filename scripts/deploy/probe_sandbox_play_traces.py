#!/usr/bin/env python3
"""Read recent music_web play traces from sandbox (incl. Now Playing diagnostics)."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DEPLOY = ROOT / "scripts" / "deploy"
sys.path.insert(0, str(DEPLOY))

from deploy import ensure_deploy_key, load_sandbox_secrets, resolve_sandbox_ssh, ssh_connect  # noqa: E402


def main() -> int:
    secrets = load_sandbox_secrets()
    host, user, password = resolve_sandbox_ssh(secrets)
    client = ssh_connect(host, user, ensure_deploy_key(), password)
    try:
        cmd = r"""
echo '=== journal play traces (last 40) ==='
journalctl -u camxora-api --since '90 min ago' | grep music_web_play_trace | tail -40
echo ''
echo '=== crios_sync_diag + crios_hold_event (last 30) ==='
sudo -u postgres psql -d camxora_platform -t -c \
  "SELECT to_char(created_at,'YYYY-MM-DD HH24:MI:SS'), event, left(coalesce(detail,''),220)
   FROM playback_events
   WHERE event IN ('crios_sync_diag','crios_hold_event')
   ORDER BY id DESC LIMIT 30;"
echo ''
echo '=== crios flags (last 20) ==='
sudo -u postgres psql -d camxora_platform -t -c \
  "SELECT to_char(created_at,'HH24:MI:SS'), event, left(coalesce(detail,''),200)
   FROM playback_events
   WHERE event LIKE 'crios_%' AND detail LIKE '%flags=%'
   ORDER BY id DESC LIMIT 20;"
echo ''
sudo -u postgres psql -d camxora_platform -t -c \
  "SELECT to_char(created_at,'YYYY-MM-DD HH24:MI:SS'), event, left(coalesce(detail,''),200)
   FROM playback_events
   WHERE event IN ('now_playing_diag','media_element_event')
   ORDER BY id DESC LIMIT 25;"
echo ''
echo '=== mismatch flags (last 15) ==='
sudo -u postgres psql -d camxora_platform -t -c \
  "SELECT to_char(created_at,'HH24:MI:SS'), event, left(coalesce(detail,''),180)
   FROM playback_events
   WHERE detail LIKE '%flags=%'
   ORDER BY id DESC LIMIT 15;"
echo ''
echo '=== all playback_events (last 20) ==='
sudo -u postgres psql -d camxora_platform -t -c \
  "SELECT to_char(created_at,'HH24:MI:SS'), event, left(coalesce(detail,''),120)
   FROM playback_events ORDER BY id DESC LIMIT 20;"
"""
        _, stdout, stderr = client.exec_command(cmd, timeout=90)
        print(stdout.read().decode("utf-8", errors="replace"))
        err = stderr.read().decode("utf-8", errors="replace")
        if err.strip():
            print(err, file=sys.stderr)
        return 0
    finally:
        client.close()


if __name__ == "__main__":
    raise SystemExit(main())
