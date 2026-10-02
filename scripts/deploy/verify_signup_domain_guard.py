#!/usr/bin/env python3
"""Verify signup domain guard logic probe using the camxora venv python."""
from __future__ import annotations

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / ".venv" / "Lib" / "site-packages"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from deploy import ensure_deploy_key, load_production_secrets, resolve_production_ssh, ssh_connect

PRODUCTION_HOST = "82.197.71.248"

CMD = r"""
set -e
PY=/opt/camxora/repo/platform_api/.venv/bin/python
echo "service_python=$PY"
test -x "$PY"

sudo -u postgres psql -d camxora_platform -P pager=off -c "
SELECT 'guard count bowlfuel.com' AS label, count(*)::int AS n
FROM users u
WHERE u.deleted_at IS NULL AND u.status='active'
  AND lower(split_part(u.email,'@',2))='bowlfuel.com'
  AND 'music_web' = ANY(u.products)
  AND NOT EXISTS (SELECT 1 FROM licenses l WHERE l.user_id=u.id AND l.status='active');
"

cd /opt/camxora/repo/platform_api
"$PY" -u - <<'PY'
import asyncio, json, sys
sys.path.insert(0, "/opt/camxora/repo")
import platform_api.services.signup_domain_guard as g
import platform_api.dependencies as deps

class FakePool:
    def __init__(self, settings, count):
        self._s = settings
        self._count = count
    async def fetchval(self, query, *params):
        if params and params[0] in self._s:
            return self._s[params[0]]
        return self._count

SETTINGS = {
    "signup_blocked_email_domains": json.dumps(["bowlfuel.com", "beiwoh.com"]),
    "signup_trusted_email_domains": json.dumps(["gmail.com", "camxora.com"]),
    "signup_max_free_accounts_per_domain": "3",
}

def run(case, coro, expect):
    try:
        asyncio.run(coro())
        ok = expect == "allow"
    except Exception as e:
        msg = str(e)
        ok = (expect == "raise" and "not allowed" in msg) or (expect == "capped" and "Too many free" in msg)
    print(("PASS" if ok else "FAIL"), case)
    if not ok:
        sys.exit(1)

async def c1(): await g.enforce_signup_domain_guard("probe1@bowlfuel.com", "music_web")
deps.get_db_pool = lambda: FakePool(SETTINGS, 0)
run("blocked-domain rejected", c1, "raise")

async def c2(): await g.enforce_signup_domain_guard("user@gmail.com", "music_web")
deps.get_db_pool = lambda: FakePool(SETTINGS, 0)
run("trusted-domain allowed", c2, "allow")

async def c3(): await g.enforce_signup_domain_guard("user@unknownfarm.com", "music_web")
deps.get_db_pool = lambda: FakePool(SETTINGS, 3)
run("over-cap rejected", c3, "capped")

async def c4(): await g.enforce_signup_domain_guard("user@unknownfarm2.com", "music_web")
deps.get_db_pool = lambda: FakePool(SETTINGS, 2)
run("under-cap allowed", c4, "allow")

async def c5(): await g.enforce_signup_domain_guard("probe1@bowlfuel.com", "studio")
run("non-music product skipped", c5, "allow")

async def c6(): await g.enforce_signup_domain_guard("", "music_web")
run("empty email ignored", c6, "allow")

async def c7(): await g.enforce_signup_domain_guard("user@camxora.com", "music_web")
run("own-domain trusted allowed", c7, "allow")
print("GUARD_PROBE_ALL_OK")
PY
echo VERIFY_DONE
"""


def run_cmd(client, cmd: str, timeout: int = 60) -> str:
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
        print(run_cmd(client, CMD, timeout=60), flush=True)
    finally:
        client.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
