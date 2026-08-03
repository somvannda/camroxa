#!/usr/bin/env python3
"""Pull live production worker logs + job_queue snapshot."""
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
echo === UNIT ===
systemctl is-active camxora-worker camxora-api
systemctl show camxora-worker -p MainPID -p ActiveEnterTimestamp -p NRestarts --no-pager
echo === PROCESS ===
ps -eo pid,pcpu,pmem,etime,cmd | grep -E 'platform_api.worker|uvicorn platform_api' | grep -v grep
echo === QUEUE SUMMARY ===
sudo -u postgres psql -d camxora_platform -c "SELECT status, count(1) AS n FROM job_queue GROUP BY 1 ORDER BY 1;"
sudo -u postgres psql -d camxora_platform -c "SELECT job_type, status, priority, count(1) AS n FROM job_queue WHERE status IN ('queued','delayed','running') GROUP BY 1,2,3 ORDER BY priority DESC, 1, 2;"
echo === RUNNING NOW ===
sudo -u postgres psql -d camxora_platform -c "SELECT id, job_type, priority, locked_by, attempts, batch_id, song_id, locked_at, EXTRACT(EPOCH FROM (NOW()-locked_at))::int AS locked_s FROM job_queue WHERE status='running' ORDER BY locked_at;"
echo === OLDEST CLAIMABLE ===
sudo -u postgres psql -d camxora_platform -c "SELECT id, job_type, status, priority, batch_id, created_at, EXTRACT(EPOCH FROM (NOW()-created_at))::int AS age_s, left(coalesce(last_error,''),100) AS err FROM job_queue WHERE status IN ('queued','delayed') AND run_after <= NOW() ORDER BY priority DESC, created_at ASC LIMIT 20;"
echo === RECENT DONE/FAIL ===
sudo -u postgres psql -d camxora_platform -c "SELECT job_type, status, priority, batch_id, updated_at, left(coalesce(last_error,''),80) AS err FROM job_queue WHERE status IN ('done','failed') ORDER BY updated_at DESC LIMIT 15;"
echo === WORKER LOG LAST 80 ===
journalctl -u camxora-worker -n 80 --no-pager --no-hostname
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
        sys.stdout.write(out.decode(errors="replace"))
    finally:
        client.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
