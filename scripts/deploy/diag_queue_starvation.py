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
echo === QUEUE BY TYPE ===
sudo -u postgres psql -d camxora_platform -c "SELECT job_type, status, priority, count(1) AS n FROM job_queue GROUP BY 1,2,3 ORDER BY priority DESC, 1,2;"
echo === PENDING BATCHES JOBS ===
sudo -u postgres psql -d camxora_platform -c "SELECT j.id, j.job_type, j.status, j.priority, j.batch_id, j.attempts, left(coalesce(j.last_error,''),80) AS err, j.created_at FROM job_queue j WHERE j.batch_id IN ('50edc218-ae67-401e-abb3-516bad8c5e29','6eaf575b-b482-4970-b298-faa47b20ba0f','5793825e-f6d0-42ca-9ad2-ba46149e5e66','81428eab-ddfb-4ebc-b8b2-1f84e12562c7') ORDER BY j.created_at;"
echo === OLDEST QUEUED ===
sudo -u postgres psql -d camxora_platform -c "SELECT id, job_type, status, priority, batch_id, created_at, EXTRACT(EPOCH FROM (NOW()-created_at))::int AS age_s FROM job_queue WHERE status IN ('queued','delayed') ORDER BY priority DESC, created_at ASC LIMIT 25;"
echo === BATCH SONG BREAKDOWN ===
sudo -u postgres psql -d camxora_platform -c "SELECT batch_id, status, count(1) FROM songs WHERE batch_id IN ('50edc218-ae67-401e-abb3-516bad8c5e29','6eaf575b-b482-4970-b298-faa47b20ba0f','5793825e-f6d0-42ca-9ad2-ba46149e5e66','81428eab-ddfb-4ebc-b8b2-1f84e12562c7') GROUP BY 1,2 ORDER BY 1,2;"
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
        chan.settimeout(60)
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
