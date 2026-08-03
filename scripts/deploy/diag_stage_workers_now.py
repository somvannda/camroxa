#!/usr/bin/env python3
"""Check production stage workers + queued jobs right now."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DEPLOY = ROOT / "scripts" / "deploy"
sys.path.insert(0, str(DEPLOY / ".venv" / "Lib" / "site-packages"))
sys.path.insert(0, str(DEPLOY))

from deploy import ensure_deploy_key, ssh_connect  # noqa: E402

PRODUCTION_HOST = "82.197.71.248"
CMD = r"""
set +e
echo === UNIT STATUS ===
systemctl is-active camxora-api camxora-worker 2>/dev/null
systemctl list-units 'camxora-worker*' --all --no-pager --no-legend
echo === ENABLED ===
systemctl list-unit-files 'camxora-worker*' --no-pager --no-legend
echo === QUEUE ===
sudo -u postgres psql -d camxora_platform -c "SELECT job_type, status, count(1) AS n FROM job_queue GROUP BY 1,2 ORDER BY 1,2;"
sudo -u postgres psql -d camxora_platform -c "SELECT id, job_type, status, attempts, priority, last_error, created_at FROM job_queue WHERE status IN ('queued','leased','running') ORDER BY priority ASC, created_at ASC LIMIT 30;"
echo === RECENT WORKER JOURNALS ===
for u in camxora-worker camxora-worker-draft@1 camxora-worker-draft@2 camxora-worker-suno@1 camxora-worker-images@1; do
  echo -- $u --
  systemctl is-active $u 2>/dev/null || true
  journalctl -u $u -n 8 --no-pager --no-hostname 2>/dev/null | tail -8
done
echo === PROCESS ===
ps aux | grep -E 'platform_api.worker|worker.py' | grep -v grep
echo DONE
"""


def load_production() -> dict[str, str]:
    data: dict[str, str] = {}
    for line in (ROOT / ".deploy" / "secrets.production.env").read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        data[key.strip()] = value.strip()
    return data


def main() -> int:
    secrets = load_production()
    host = secrets.get("PRODUCTION_VPS_HOST") or secrets["VPS_HOST"]
    user = secrets.get("PRODUCTION_VPS_USER") or secrets["VPS_USER"]
    password = secrets.get("PRODUCTION_VPS_PASSWORD") or secrets.get("VPS_PASSWORD")
    if host != PRODUCTION_HOST:
        raise SystemExit(f"Refusing non-production host: {host}")
    client = ssh_connect(host, user, ensure_deploy_key(), password)
    try:
        chan = client.get_transport().open_session()
        chan.settimeout(90)
        chan.exec_command(CMD)
        out = b""
        while True:
            if chan.recv_ready():
                chunk = chan.recv(65535)
                if not chunk:
                    break
                out += chunk
            if chan.exit_status_ready():
                while chan.recv_ready():
                    out += chan.recv(65535)
                break
        print(out.decode(errors="replace"))
    finally:
        client.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
