#!/usr/bin/env python3
"""Diagnose production pipeline/progress after job-queue deploys."""
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
echo === SERVICES ===
systemctl is-active camxora-api camxora-worker nginx
echo === WORKER TAIL ===
journalctl -u camxora-worker -n 50 --no-pager
echo === API ERRORS RECENT ===
journalctl -u camxora-api --since "3 hours ago" --no-pager | grep -iE "ERROR|Exception|Traceback|progress|job_queue|fanout|Unsupported" | tail -60
echo === RECENT BATCHES ===
sudo -u postgres psql -d camxora_platform -c "SELECT id, status, song_count, created_at, auto_gsuno, auto_gen_image FROM batches ORDER BY created_at DESC LIMIT 15;"
echo === RECENT SONG STATUSES ===
sudo -u postgres psql -d camxora_platform -c "SELECT status, count(1) AS n FROM songs WHERE created_at > NOW() - INTERVAL '2 days' GROUP BY status ORDER BY n DESC;"
echo === JOB QUEUE ALL ===
sudo -u postgres psql -d camxora_platform -c "SELECT job_type, status, count(1) AS n FROM job_queue GROUP BY 1,2 ORDER BY 1,2;"
sudo -u postgres psql -d camxora_platform -c "SELECT id, job_type, status, attempts, last_error, created_at, updated_at FROM job_queue ORDER BY created_at DESC LIMIT 20;"
echo === PROGRESS SMOKE ===
curl -sS -m 10 -o /tmp/health.json -w "health:%{http_code}\n" http://127.0.0.1:8100/health
python3 - <<'PY'
import json
from pathlib import Path
p=Path('/opt/camxora/repo/platform_api/worker.py')
text=p.read_text(encoding='utf-8', errors='replace')
for needle in ['fanout_draft_jobs','JOB_RUN_IMAGE_JOBS','draft','execute_batch']:
    print(needle, 'YES' if needle in text else 'NO')
bs=Path('/opt/camxora/repo/platform_api/services/batch_service.py').read_text(encoding='utf-8', errors='replace')
print('fanout_draft_jobs_def', 'async def fanout_draft_jobs' in bs)
print('schedule_image_enqueue', 'JOB_RUN_IMAGE_JOBS' in bs or 'run_image_jobs' in bs)
PY
echo === DEPLOYED PROGRESS ENSURE ===
python3 - <<'PY'
from pathlib import Path
t=Path('/opt/camxora/repo/platform_api/routers/progress.py').read_text(encoding='utf-8', errors='replace')
print('ensure_batch_image_jobs', t.count('ensure_batch_image_jobs'))
print('missing image_jobs only', 'missing' in t.lower() and 'image_jobs' in t)
# show nearby snippet
idx=t.find('ensure_batch_image_jobs')
print(t[max(0,idx-200):idx+400] if idx>=0 else 'NOT FOUND')
PY
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
        _, stdout, stderr = client.exec_command(CMD, get_pty=True, timeout=180)
        print(stdout.read().decode(errors="replace"))
        err = stderr.read().decode(errors="replace")
        if err.strip():
            print(err, file=sys.stderr)
    finally:
        client.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
