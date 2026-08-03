#!/usr/bin/env python3
from __future__ import annotations
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
DEPLOY = ROOT / "scripts" / "deploy"
sys.path.insert(0, str(DEPLOY / ".venv" / "Lib" / "site-packages"))
sys.path.insert(0, str(DEPLOY))
from deploy import ensure_deploy_key, ssh_connect
PRODUCTION_HOST = "82.197.71.248"
CMD = r"""
set +e
grep -n 'include_router\|admin_pipeline\|from platform_api.routers' /opt/camxora/repo/platform_api/main.py | head -100
echo ===
grep -n 'admin_pipeline\|pipeline' /opt/camxora/repo/platform_api/wire_dependencies.py | head -40
echo ===
python3 - <<'PY'
import json,urllib.request
d=json.load(urllib.request.urlopen('http://127.0.0.1:8100/openapi.json', timeout=10))
print([p for p in d.get('paths',{}) if 'pipeline' in p][:40])
PY
"""
def load_production():
    data={}
    for line in (ROOT/'.deploy'/'secrets.production.env').read_text(encoding='utf-8').splitlines():
        line=line.strip()
        if not line or line.startswith('#') or '=' not in line: continue
        k,_,v=line.partition('='); data[k.strip()]=v.strip()
    return data
def main():
    s=load_production(); host=s.get('PRODUCTION_VPS_HOST') or s['VPS_HOST']
    if host!=PRODUCTION_HOST: raise SystemExit(host)
    c=ssh_connect(host,s.get('PRODUCTION_VPS_USER') or s['VPS_USER'],ensure_deploy_key(),s.get('PRODUCTION_VPS_PASSWORD') or s.get('VPS_PASSWORD'))
    try:
        ch=c.get_transport().open_session(); ch.settimeout(90); ch.exec_command(CMD)
        out=b''
        while True:
            if ch.recv_ready():
                x=ch.recv(65535)
                if not x: break
                out+=x
            if ch.exit_status_ready():
                while ch.recv_ready(): out+=ch.recv(65535)
                break
        print(out.decode(errors='replace'))
    finally:
        c.close()
    return 0
if __name__=='__main__':
    raise SystemExit(main())
