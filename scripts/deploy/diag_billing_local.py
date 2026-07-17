#!/usr/bin/env python3
"""Test draft + billing on sandbox via localhost API with fresh user."""

from __future__ import annotations

import json
import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / ".venv" / "Lib" / "site-packages"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from deploy import ensure_deploy_key, load_secrets, ssh_connect  # noqa: E402


def main() -> int:
    secrets = load_secrets()
    client = ssh_connect(secrets["VPS_HOST"], secrets["VPS_USER"], ensure_deploy_key(), None)
    email = f"diag.{uuid.uuid4().hex[:8]}@example.com"
    password = "DiagTest12345!!"
    cmd = f"""
set -e
EMAIL={email!r}
PASS={password!r}
COOKIE=/tmp/diag-cookies.txt
rm -f $COOKIE

register=$(curl -s -w '\\nHTTP:%{{http_code}}' -X POST http://127.0.0.1:8100/api/v1/auth/register \
  -H 'Content-Type: application/json' -H 'X-Portal-Context: user' \
  -d "{{\\"email\\":\\"$EMAIL\\",\\"password\\":\\"$PASS\\",\\"display_name\\":\\"Diag User\\"}}")
echo "REGISTER: $register" | tail -2

login=$(curl -s -c $COOKIE -w '\\nHTTP:%{{http_code}}' -X POST http://127.0.0.1:8100/api/v1/auth/login \
  -H 'Content-Type: application/json' -H 'X-Portal-Context: user' \
  -d "{{\\"email\\":\\"$EMAIL\\",\\"password\\":\\"$PASS\\"}}")
echo "LOGIN: $login" | tail -2

me=$(curl -s -b $COOKIE -w '\\nHTTP:%{{http_code}}' http://127.0.0.1:8100/api/v1/users/me -H 'X-Portal-Context: user')
echo "ME: $me" | tail -2

draft=$(curl -s -b $COOKIE -w '\\nHTTP:%{{http_code}}' http://127.0.0.1:8100/api/v1/channel-setup/draft -H 'X-Portal-Context: user')
echo "DRAFT: $draft" | tail -2

plan_id=$(curl -sf -b $COOKIE http://127.0.0.1:8100/api/v1/plans/public -H 'X-Portal-Context: user' | python3 -c "import sys,json; ps=[p for p in json.load(sys.stdin) if p.get('effective_price_cents',0)>0]; print(ps[0]['id'] if ps else '')")
echo "PLAN_ID=$plan_id"

pay=$(curl -s -b $COOKIE -w '\\nHTTP:%{{http_code}}' -X POST http://127.0.0.1:8100/api/v1/billing/payments \
  -H 'Content-Type: application/json' -H 'X-Portal-Context: user' \
  -d "{{\\"plan_id\\":\\"$plan_id\\"}}")
echo "PAYMENT: $pay"

echo '--- cutluy direct probe ---'
SECRET=$(sudo -u camxora bash -lc 'set -a && source /opt/camxora/repo/platform_api/.env && set +a && /opt/camxora/repo/platform_api/.venv/bin/python - <<"PY"
import asyncio, asyncpg, os
async def main():
    dsn=os.environ["PLATFORM_DATABASE_URL"].replace("postgresql+asyncpg://","postgresql://",1)
    conn=await asyncpg.connect(dsn)
    row=await conn.fetchrow("SELECT value FROM system_settings WHERE key=$1","billing.cutluy.secret_key")
    link=await conn.fetchrow("SELECT value FROM system_settings WHERE key=$1","billing.cutluy.payment_link_id")
    print((row["value"] if row else "") + "|" + (link["value"] if link else ""))
    await conn.close()
asyncio.run(main())
PY')
API_KEY=${{SECRET%%|*}}
LINK_ID=${{SECRET#*|}}
echo "link_id=$LINK_ID"
curl -s -w '\\nHTTP:%{{http_code}}' -X POST https://cutluy.com/v1/payments \
  -H "Authorization: Bearer $API_KEY" -H 'Content-Type: application/json' \
  -d "{{\\"amount\\":1.0,\\"reference_id\\":\\"diag-$(date +%s)\\",\\"payment_link_id\\":\\"$LINK_ID\\",\\"metadata\\":{{\\"test\\":true}}}}" | tail -5

echo '--- recent journal ---'
journalctl -u camxora-api -n 40 --no-pager | tail -20
"""
    _, stdout, stderr = client.exec_command(cmd, get_pty=True)
    out = stdout.read().decode("utf-8", errors="replace")
    err = stderr.read().decode("utf-8", errors="replace")
    print(out)
    if err.strip():
        print("STDERR:", err)
    client.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
