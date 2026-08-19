#!/usr/bin/env python3
"""Read-only production check: unusual free signups burning web-music credits."""

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
echo '=== signup_mode / daily free credits / email confirm setting ==='
sudo -u postgres psql -d camxora_platform -c "
SELECT key, value FROM system_settings
WHERE key IN (
  'signup_mode',
  'web_music_free_daily_credits',
  'web_music_free_daily_limit'
)
ORDER BY 1;
"

echo '=== users.email_confirmed column? ==='
sudo -u postgres psql -d camxora_platform -c "
SELECT column_name, data_type, column_default
FROM information_schema.columns
WHERE table_name = 'users' AND column_name IN ('email_confirmed','status','created_at')
ORDER BY 1;
"

echo '=== deployed auth gate / turnstile ==='
python3 - <<'PY'
from pathlib import Path
auth = Path('/opt/camxora/repo/platform_api/middleware/auth.py').read_text(encoding='utf-8', errors='replace')
router = Path('/opt/camxora/repo/platform_api/routers/auth.py').read_text(encoding='utf-8', errors='replace')
print('HAS email_confirmed gate:', 'Confirm your email before using Camxora' in auth)
print('HAS _UNCONFIRMED_ALLOWED_PATHS:', '_UNCONFIRMED_ALLOWED_PATHS' in auth)
print('HAS turnstile import:', 'turnstile_service' in router)
print('HAS optional turnstile (if token):', 'if request.cf_turnstile_response:' in router)
print('HAS required turnstile:', 'Turnstile token is required' in router or 'cf_turnstile_response is required' in router)
print('HAS register rate limit:', 'register' in router and 'check_for_endpoint' in router)
PY

echo '=== signup volume last 21 days ==='
sudo -u postgres psql -d camxora_platform -c "
SELECT (created_at AT TIME ZONE 'Asia/Phnom_Penh')::date AS day,
       COUNT(*) AS signups,
       COUNT(*) FILTER (WHERE COALESCE(email_confirmed, true) = false) AS unconfirmed,
       COUNT(*) FILTER (WHERE role = 'admin') AS admins
FROM users
WHERE created_at >= NOW() - INTERVAL '21 days'
  AND status <> 'deleted'
GROUP BY 1
ORDER BY 1 DESC;
"

echo '=== last 48h signups vs lifetime ==='
sudo -u postgres psql -d camxora_platform -c "
SELECT
  COUNT(*) FILTER (WHERE created_at >= NOW() - INTERVAL '48 hours') AS last_48h,
  COUNT(*) FILTER (WHERE created_at >= NOW() - INTERVAL '7 days') AS last_7d,
  COUNT(*) FILTER (WHERE created_at >= NOW() - INTERVAL '30 days') AS last_30d,
  COUNT(*) AS all_users
FROM users
WHERE status <> 'deleted' AND role = 'user';
"

echo '=== email domain clusters (last 14d user signups) ==='
sudo -u postgres psql -d camxora_platform -c "
SELECT LOWER(split_part(email, '@', 2)) AS domain,
       COUNT(*) AS n,
       COUNT(*) FILTER (WHERE created_at >= NOW() - INTERVAL '48 hours') AS last_48h
FROM users
WHERE status <> 'deleted' AND role = 'user'
  AND created_at >= NOW() - INTERVAL '14 days'
GROUP BY 1
ORDER BY n DESC
LIMIT 25;
"

echo '=== disposable / plus-alias / sequential patterns (last 14d) ==='
sudo -u postgres psql -d camxora_platform -c "
WITH recent AS (
  SELECT id, email, display_name, created_at, COALESCE(email_confirmed, true) AS email_confirmed
  FROM users
  WHERE status <> 'deleted' AND role = 'user'
    AND created_at >= NOW() - INTERVAL '14 days'
)
SELECT
  COUNT(*) AS recent,
  COUNT(*) FILTER (WHERE email ~* '\\+') AS plus_alias,
  COUNT(*) FILTER (
    WHERE LOWER(split_part(email,'@',2)) IN (
      'mailinator.com','guerrillamail.com','tempmail.com','temp-mail.org','10minutemail.com',
      'yopmail.com','trashmail.com','sharklasers.com','guerrillamailblock.com','dispostable.com',
      'mailnesia.com','maildrop.cc','throwaway.email','getnada.com','inboxkitten.com',
      'tempail.com','moakt.com','emailondeck.com','fakeinbox.com','mintemail.com'
    )
  ) AS known_disposable,
  COUNT(*) FILTER (WHERE email ~* '^[a-z0-9._%+-]+\\+[0-9]+@') AS numbered_plus,
  COUNT(*) FILTER (WHERE display_name ~* '^(user|test|asdf|qwerty|admin)[0-9]*$') AS generic_names
FROM recent;
"

echo '=== same local-part prefix clusters (last 14d) ==='
sudo -u postgres psql -d camxora_platform -c "
SELECT LEFT(LOWER(split_part(email,'@',1)), 8) AS prefix8,
       COUNT(*) AS n,
       STRING_AGG(email, ', ' ORDER BY created_at DESC) AS emails
FROM users
WHERE status <> 'deleted' AND role = 'user'
  AND created_at >= NOW() - INTERVAL '14 days'
GROUP BY 1
HAVING COUNT(*) >= 3
ORDER BY n DESC
LIMIT 15;
"

echo '=== register IPs from audit_logs (last 14d) ==='
sudo -u postgres psql -d camxora_platform -c "
SELECT source_ip,
       COUNT(*) AS n,
       COUNT(DISTINCT actor_id) AS users,
       MIN(created_at) AS first_seen,
       MAX(created_at) AS last_seen
FROM audit_logs
WHERE created_at >= NOW() - INTERVAL '14 days'
  AND (
    endpoint_path ILIKE '%/auth/register%'
    OR action_type ILIKE '%register%'
  )
GROUP BY 1
ORDER BY n DESC
LIMIT 20;
"

echo '=== sample recent register audit rows ==='
sudo -u postgres psql -d camxora_platform -c "
SELECT created_at, action_type, endpoint_path, source_ip, actor_id, outcome
FROM audit_logs
WHERE created_at >= NOW() - INTERVAL '7 days'
  AND (
    endpoint_path ILIKE '%/auth/register%'
    OR action_type ILIKE '%register%'
  )
ORDER BY created_at DESC
LIMIT 15;
"

echo '=== nginx register POSTs last log (top IPs) ==='
python3 - <<'PY'
from pathlib import Path
import re, collections
paths = [
    Path('/var/log/nginx/access.log'),
    Path('/var/log/nginx/camxora-production.access.log'),
    Path('/var/log/nginx/music.camxora.com.access.log'),
]
found = False
for p in Path('/var/log/nginx').glob('*access*'):
    try:
        text = p.read_text(encoding='utf-8', errors='replace')
    except Exception as e:
        continue
    rows = [ln for ln in text.splitlines() if 'auth/register' in ln and 'POST' in ln]
    if not rows:
        continue
    found = True
    print('FILE', p, 'register_posts', len(rows))
    ips = collections.Counter()
    for ln in rows:
        ip = ln.split(' ', 1)[0]
        ips[ip] += 1
    for ip, n in ips.most_common(15):
        print(f'  {n:4d}  {ip}')
    print('  last5:')
    for ln in rows[-5:]:
        print('   ', ln[:220])
if not found:
    print('NO_NGINX_REGISTER_HITS_IN_CURRENT_ACCESS_LOGS')
    print('files', [str(p) for p in Path('/var/log/nginx').glob('*')])
PY

echo '=== free users signed up last 14d who burned credits ==='
sudo -u postgres psql -d camxora_platform -c "
SELECT
  u.email,
  u.created_at AT TIME ZONE 'Asia/Phnom_Penh' AS signed_up,
  COALESCE(u.email_confirmed, true) AS email_confirmed,
  u.status,
  COALESCE(life.used,0) AS lifetime_credits,
  COALESCE(life.max_day,0) AS max_day,
  COALESCE(today.credits_used,0) AS today_used,
  COALESCE(today.generation_count,0) AS today_gen,
  EXISTS (
    SELECT 1 FROM web_subscriptions ws
    WHERE ws.user_id = u.id AND ws.status = 'active'
      AND (ws.cancel_at_period_end = false OR ws.current_period_end > NOW())
  ) AS has_paid_music
FROM users u
LEFT JOIN LATERAL (
  SELECT COALESCE(SUM(credits_used),0)::int AS used,
         COALESCE(MAX(credits_used),0)::int AS max_day
  FROM web_music_daily_usage d WHERE d.user_id = u.id
) life ON true
LEFT JOIN web_music_daily_usage today
  ON today.user_id = u.id
 AND today.usage_date = (NOW() AT TIME ZONE 'Asia/Phnom_Penh')::date
WHERE u.role = 'user'
  AND u.status <> 'deleted'
  AND u.created_at >= NOW() - INTERVAL '14 days'
  AND COALESCE(life.used,0) > 0
  AND NOT EXISTS (
    SELECT 1 FROM web_subscriptions ws
    WHERE ws.user_id = u.id AND ws.status = 'active'
      AND (ws.cancel_at_period_end = false OR ws.current_period_end > NOW())
  )
ORDER BY life.used DESC, u.created_at DESC
LIMIT 40;
"

echo '=== new free signups last 14d: burned vs idle ==='
sudo -u postgres psql -d camxora_platform -c "
WITH recent AS (
  SELECT u.id
  FROM users u
  WHERE u.role = 'user' AND u.status <> 'deleted'
    AND u.created_at >= NOW() - INTERVAL '14 days'
    AND NOT EXISTS (
      SELECT 1 FROM web_subscriptions ws
      WHERE ws.user_id = u.id AND ws.status = 'active'
        AND (ws.cancel_at_period_end = false OR ws.current_period_end > NOW())
    )
)
SELECT
  COUNT(*) AS free_signups_14d,
  COUNT(*) FILTER (WHERE COALESCE(life.used,0) > 0) AS burned_any,
  COUNT(*) FILTER (WHERE COALESCE(life.used,0) >= 50) AS burned_50_plus,
  COALESCE(SUM(life.used),0)::int AS total_credits_burned
FROM recent r
JOIN LATERAL (
  SELECT COALESCE(SUM(credits_used),0)::int AS used
  FROM web_music_daily_usage d WHERE d.user_id = r.id
) life ON true;
"

echo '=== today free credit spend ==='
sudo -u postgres psql -d camxora_platform -c "
SELECT
  COUNT(*) AS free_users_today,
  COALESCE(SUM(d.credits_used),0)::int AS credits,
  COALESCE(SUM(d.generation_count),0)::int AS gens
FROM web_music_daily_usage d
WHERE d.usage_date = (NOW() AT TIME ZONE 'Asia/Phnom_Penh')::date
  AND NOT EXISTS (
    SELECT 1 FROM web_subscriptions ws
    WHERE ws.user_id = d.user_id AND ws.status = 'active'
      AND (ws.cancel_at_period_end = false OR ws.current_period_end > NOW())
  );
"

echo DIAG_SIGNUP_ABUSE_DONE
"""


def run_cmd(client, cmd: str, timeout: int = 120) -> str:
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
    print(f"Read-only check on {user}@{host}", flush=True)
    client = ssh_connect(host, user, ensure_deploy_key(), password)
    print("SSH connected", flush=True)
    try:
        print(run_cmd(client, CMD, timeout=110), flush=True)
    finally:
        client.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
