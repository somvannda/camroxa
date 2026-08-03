#!/usr/bin/env python3
"""Live progress/pipeline snapshot for production."""
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
echo === WORKERS ===
systemctl is-active camxora-worker-draft@{1..4} camxora-worker-suno@{1..2} camxora-worker-images@{1..2} | tr '\n' ' '; echo
echo === IMAGE JOBS RECENT ===
sudo -u postgres psql -d camxora_platform -c "SELECT status, count(1) FROM image_jobs WHERE created_at > NOW() - INTERVAL '2 days' GROUP BY 1 ORDER BY 1;"
echo === SONGS BY STATUS LAST 2D ===
sudo -u postgres psql -d camxora_platform -c "SELECT status, count(1) FROM songs WHERE created_at > NOW() - INTERVAL '2 days' GROUP BY 1 ORDER BY 2 DESC;"
echo === PARTIAL BATCHES ===
sudo -u postgres psql -d camxora_platform -c "SELECT id, status, song_count, created_at FROM batches WHERE status IN ('pending','processing','partial','failed') ORDER BY created_at DESC LIMIT 20;"
echo === QUEUE LIVE ===
sudo -u postgres psql -d camxora_platform -c "SELECT job_type, status, count(1) FROM job_queue WHERE status <> 'done' GROUP BY 1,2;"
echo === WORKER HEARTBEAT ===
journalctl -u 'camxora-worker-*' --since '10 min ago' --no-pager --no-hostname | grep -iE 'draining|claimed|done|ERROR|Exception|lease|Job ' | tail -40
echo === METRICS ===
curl -sS -m 5 http://127.0.0.1:8100/health; echo
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
