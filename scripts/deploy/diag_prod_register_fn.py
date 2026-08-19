#!/usr/bin/env python3
"""Read-only: dump production register() invite/turnstile logic."""

from __future__ import annotations

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / ".venv" / "Lib" / "site-packages"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from deploy import ensure_deploy_key, load_production_secrets, resolve_production_ssh, ssh_connect

PRODUCTION_HOST = "82.197.71.248"

CMD = r"""
python3 - <<'PY'
from pathlib import Path
text = Path('/opt/camxora/repo/platform_api/routers/auth.py').read_text(encoding='utf-8', errors='replace')
start = text.find('async def register(')
end = text.find('\n@router.', start + 1)
print(text[start:end if end > start else start+8000])
print('--- get_signup_mode in invitation service ---')
svc = Path('/opt/camxora/repo/platform_api/services/invitation_code_service.py').read_text(encoding='utf-8', errors='replace')
s = svc.find('async def get_signup_mode')
print(svc[s:s+700])
PY

echo '=== redemptions ==='
sudo -u postgres psql -d camxora_platform -c "
SELECT r.redeemed_at, r.user_id, u.email
FROM invitation_code_redemptions r
LEFT JOIN users u ON u.id = r.user_id
ORDER BY r.redeemed_at DESC
LIMIT 20;
"

echo '=== music_web register invitation UI ==='
python3 - <<'PY'
from pathlib import Path
p = Path('/opt/camxora/repo/music_web/src/app/register/page.tsx')
print('exists', p.exists())
text = p.read_text(encoding='utf-8', errors='replace') if p.exists() else ''
print('HAS invitationCode', 'invitationCode' in text)
print('HAS invitation_code', 'invitation_code' in text)
print('HAS TurnstileWidget', 'TurnstileWidget' in text)
print('HAS cf_turnstile', 'cf_turnstile' in text)
# also auth-api
p2 = Path('/opt/camxora/repo/music_web/src/lib/auth-api.ts')
t2 = p2.read_text(encoding='utf-8', errors='replace') if p2.exists() else ''
print('auth-api HAS invitation_code', 'invitation_code' in t2)
print('auth-api HAS cf_turnstile', 'cf_turnstile' in t2)
print('--- register page excerpt ---')
print(text[:2500])
PY
"""


def run_cmd(client, cmd: str, timeout: int = 40) -> str:
    chan = client.get_transport().open_session()
    chan.settimeout(timeout)
    chan.exec_command(cmd)
    out = b""
    started = time.time()
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
        if time.time() - started > timeout:
            out += b"\nTIMEOUT\n"
            break
        time.sleep(0.1)
    return out.decode("utf-8", errors="replace")


def main() -> int:
    secrets = load_production_secrets()
    host, user, password = resolve_production_ssh(secrets)
    if host != PRODUCTION_HOST:
        raise SystemExit(f"Refusing non-production host: {host}")
    client = ssh_connect(host, user, ensure_deploy_key(), password)
    try:
        print(run_cmd(client, CMD, timeout=35), flush=True)
    finally:
        client.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
