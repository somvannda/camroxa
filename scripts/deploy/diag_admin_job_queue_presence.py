#!/usr/bin/env python3
"""Check whether admin Job Queue UI is present on production."""
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
echo === ADMIN DIST ===
ls -la /opt/camxora/admin_portal/dist/index.html 2>/dev/null
ls /opt/camxora/admin_portal/dist/assets 2>/dev/null | wc -l
echo === GREP DIST ===
grep -R -l 'job-queue' /opt/camxora/admin_portal/dist/assets 2>/dev/null | head -5
grep -R -o 'Job Queue\|/job-queue' /opt/camxora/admin_portal/dist/assets 2>/dev/null | head -20
echo === GREP SRC ===
test -f /opt/camxora/admin_portal/src/pages/job-queue/index.tsx && echo src_job_queue=YES || echo src_job_queue=NO
grep -n 'job-queue\|Job Queue' /opt/camxora/admin_portal/src/App.tsx /opt/camxora/admin_portal/src/components/layout/sidebar.tsx 2>/dev/null | head -20
echo === API METRICS ===
curl -sS -m 5 -o /dev/null -w 'metrics:%{http_code}\n' http://127.0.0.1:8100/api/v1/admin/job-queue/metrics
echo === PROGRESS STAGES SAMPLE ===
sudo -u postgres psql -d camxora_platform -c "
SELECT b.id::text AS batch, b.status AS batch_status,
       count(*) FILTER (WHERE s.status='suno_success') AS suno_ok,
       count(*) AS songs
FROM batches b
JOIN songs s ON s.batch_id = b.id
WHERE b.created_at > NOW() - INTERVAL '3 days'
GROUP BY b.id, b.status
ORDER BY b.created_at DESC
LIMIT 12;
"
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
