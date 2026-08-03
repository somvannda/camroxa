#!/usr/bin/env python3
"""Deep-dive production platform_api instability (timeouts/502 while admin OK)."""
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
echo === NOW ===
date
uptime
free -h | head -3
echo === UNITS ===
systemctl is-active camxora-api nginx camxora-portal
systemctl show camxora-api -p ActiveEnterTimestamp -p NRestarts -p MainPID --no-pager
echo === PROCESSES ===
ps -eo pid,ppid,pcpu,pmem,rss,etime,cmd | grep -E 'uvicorn platform_api|nginx:|postgres|redis' | grep -v grep | head -40
echo === LISTEN ===
ss -lntp | grep -E ':8100|:443|:80' || netstat -lntp 2>/dev/null | grep -E ':8100|:443'
echo === LOCAL HEALTH ===
curl -sS -m 5 -w ' local_health:%{http_code} t=%{time_total}\n' http://127.0.0.1:8100/health || echo local_health_fail
curl -sS -m 5 -w ' public_health:%{http_code} t=%{time_total}\n' https://api.camxora.com/health -o /tmp/h.json; head -c 200 /tmp/h.json; echo
curl -sS -m 5 -w ' admin:%{http_code} t=%{time_total}\n' -o /dev/null https://admin.camxora.com/
echo === API RESTARTS LAST 24H ===
journalctl -u camxora-api --since '24 hours ago' --no-pager -o short-iso | grep -Ei 'Started|Stopped|Failed|Main process exited|Watchdog|OOM|Killed|ERROR|Traceback|Worker|timeout|Too many|pool|Connection' | tail -80
echo === API LAST 60 LINES ===
journalctl -u camxora-api -n 60 --no-pager --no-hostname
echo === NGINX 502/UPSTREAM LAST 6H ===
journalctl -u nginx --since '6 hours ago' --no-pager 2>/dev/null | grep -Ei '502|upstream|timed out|connect\(\) failed|8100' | tail -40
ls -la /var/log/nginx/ 2>/dev/null | head -20
grep -Eh 'api\.camxora|8100|upstream timed out|connect\(\) failed|502' /var/log/nginx/error.log /var/log/nginx/*error*.log 2>/dev/null | tail -50
echo === DMESG OOM/NET ===
dmesg -T 2>/dev/null | grep -Ei 'oom|killed process|out of memory|camxora|uvicorn' | tail -20
echo === DB CONNECTIONS ===
sudo -u postgres psql -d camxora_platform -c "SELECT state, count(*) FROM pg_stat_activity WHERE datname='camxora_platform' GROUP BY 1 ORDER BY 1;" 2>/dev/null
sudo -u postgres psql -d camxora_platform -c "SELECT count(*) AS total, count(*) FILTER (WHERE state='active') AS active FROM pg_stat_activity WHERE datname='camxora_platform';" 2>/dev/null
echo === WORKER COUNT ===
ps -eo cmd | grep -c '[p]latform_api.worker' || true
systemctl list-units 'camxora-worker*' --no-legend --no-pager | head -20
echo === NGINX API SITE ===
grep -R "api.camxora\|proxy_pass\|8100\|proxy_read\|proxy_connect\|keepalive" /etc/nginx/sites-enabled /etc/nginx/conf.d 2>/dev/null | head -60
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
        chan.settimeout(120)
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
