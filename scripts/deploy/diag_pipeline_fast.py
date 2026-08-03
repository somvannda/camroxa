#!/usr/bin/env python3
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
systemctl is-active camxora-api camxora-worker
journalctl -u camxora-worker -n 40 --no-pager --no-hostname
echo ---API---
journalctl -u camxora-api --since "2 hours ago" --no-pager --no-hostname | grep -iE "ERROR|Exception|Traceback|fanout|/progress" | tail -40
echo ---DB---
sudo -u postgres psql -d camxora_platform -Atc "SELECT count(1) FROM job_queue;"
sudo -u postgres psql -d camxora_platform -c "SELECT status, count(1) FROM batches WHERE created_at > NOW() - INTERVAL '3 days' GROUP BY 1;"
sudo -u postgres psql -d camxora_platform -c "SELECT status, count(1) FROM songs WHERE created_at > NOW() - INTERVAL '3 days' GROUP BY 1;"
sudo -u postgres psql -d camxora_platform -c "SELECT id, status, song_count, created_at FROM batches ORDER BY created_at DESC LIMIT 8;"
echo ---CODE---
grep -n "fanout_draft_jobs\|submit_suno\|_schedule_image_jobs_run" /opt/camxora/repo/platform_api/services/batch_service.py | head -20
grep -n "JOB_DRAFT\|fanout_draft\|run_image_jobs\|WORKER_JOB" /opt/camxora/repo/platform_api/worker.py | head -30
echo OK
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
        print("exit", chan.recv_exit_status())
    finally:
        client.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
