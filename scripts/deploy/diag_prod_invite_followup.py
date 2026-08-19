#!/usr/bin/env python3
"""Read-only production follow-up: invitation codes and invite-only enforcement."""

from __future__ import annotations

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / ".venv" / "Lib" / "site-packages"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from deploy import ensure_deploy_key, load_production_secrets, resolve_production_ssh, ssh_connect

PRODUCTION_HOST = "82.197.71.248"

CMD = r"""
set +e
echo '=== invitation_codes table? ==='
sudo -u postgres psql -d camxora_platform -c "\dt *invit*"
echo
sudo -u postgres psql -d camxora_platform -c "
SELECT column_name, data_type FROM information_schema.columns
WHERE table_name ILIKE '%invit%' ORDER BY table_name, ordinal_position;
"

echo '=== invitation codes usage ==='
sudo -u postgres psql -d camxora_platform -c "
SELECT id, code, label, max_uses, used_count, is_active, created_at, expires_at
FROM invitation_codes
ORDER BY created_at DESC
LIMIT 30;
" 2>/dev/null || sudo -u postgres psql -d camxora_platform -c "
SELECT * FROM invitation_codes LIMIT 20;
" 2>/dev/null || echo 'NO_INVITATION_CODES_TABLE_OR_QUERY_FAILED'

echo '=== invitation redemptions last 14d ==='
sudo -u postgres psql -d camxora_platform -c "\dt *invit*"
sudo -u postgres psql -d camxora_platform -c "
SELECT table_name FROM information_schema.tables
WHERE table_schema='public' AND table_name ILIKE '%invit%';
"

echo '=== deployed register invite check ==='
python3 - <<'PY'
from pathlib import Path
text = Path('/opt/camxora/repo/platform_api/routers/auth.py').read_text(encoding='utf-8', errors='replace')
for needle in [
    'invite_only',
    'normalized_invitation_code',
    'Invitation code is required',
    'consume_invitation_code',
    'if request.cf_turnstile_response',
    'cf_turnstile_response',
]:
    print(f'HAS {needle!r}:', needle in text)
start = text.find('async def register')
print('--- register snippet ---')
print(text[start:start+2200])
PY

echo '=== signup_mode row history? ==='
sudo -u postgres psql -d camxora_platform -c "
SELECT key, value, updated_at FROM system_settings WHERE key = 'signup_mode';
"

echo '=== music_web register invitation field ==='
grep -n "invitation\|Turnstile\|invite" /opt/camxora/repo/music_web/src/app/register/page.tsx | head -40

echo '=== all users last 48h with invite metadata ==='
sudo -u postgres psql -d camxora_platform -c "
SELECT u.email, u.created_at AT TIME ZONE 'Asia/Phnom_Penh' AS signed_up,
       u.email_confirmed, u.status
FROM users u
WHERE u.created_at >= NOW() - INTERVAL '48 hours'
  AND u.role = 'user'
ORDER BY u.created_at DESC;
"

echo '=== possible related accounts (same local-part stem) ==='
sudo -u postgres psql -d camxora_platform -c "
SELECT regexp_replace(LOWER(split_part(email,'@',1)), '[0-9]+', '', 'g') AS stem,
       COUNT(*) AS n,
       STRING_AGG(email, ', ' ORDER BY created_at) AS emails
FROM users
WHERE role='user' AND status <> 'deleted'
GROUP BY 1
HAVING COUNT(*) >= 2
ORDER BY n DESC;
"

echo DIAG_INVITE_FOLLOWUP_DONE
"""


def run_cmd(client, cmd: str, timeout: int = 90) -> str:
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
                out += chunk if False else chan.recv(65535)
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
    print(f"Read-only follow-up on {user}@{host}", flush=True)
    client = ssh_connect(host, user, ensure_deploy_key(), password)
    print("SSH connected", flush=True)
    try:
        print(run_cmd(client, CMD, timeout=80), flush=True)
    finally:
        client.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
