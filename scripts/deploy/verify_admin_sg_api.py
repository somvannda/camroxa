#!/usr/bin/env python3
"""Verify signup-domain-guard admin endpoints end-to-end with Bearer auth.

Uses a throwaway domain (sgprobe.invalid) for block/unblock round-trips and a
nonexistent domain for suspend/freeze no-ops. Leaves prod settings unchanged.
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / ".venv" / "Lib" / "site-packages"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from deploy import ensure_deploy_key, load_production_secrets, resolve_production_ssh, ssh_connect

PRODUCTION_HOST = "82.197.71.248"

CMD = r"""
cd /opt/camxora/repo/platform_api
/opt/camxora/repo/platform_api/.venv/bin/python -u - 2>&1 <<'PY'
import asyncio, sys
sys.path.insert(0, "/opt/camxora/repo")
import asyncpg
import redis.asyncio as aioredis
from platform_api.dependencies import (
    clear_connections, get_auth_service, get_settings, get_user_repo,
    set_db_pool, set_redis,
)

BASE = "http://127.0.0.1:8100/api/v1/admin/signup-domain-guard"


async def main():
    settings = get_settings()
    dsn = settings.database_url.replace("postgresql+asyncpg://", "postgresql://", 1)
    pool = await asyncpg.create_pool(dsn, min_size=1, max_size=2)
    set_db_pool(pool)
    redis_conn = aioredis.from_url(settings.redis_url, decode_responses=True)
    set_redis(redis_conn)
    try:
        email = await pool.fetchval("SELECT email FROM users WHERE role='admin' AND status='active' ORDER BY created_at LIMIT 1")
        auth = get_auth_service()
        user = await get_user_repo().get_by_email(email)
        pair = await auth.issue_token_pair_for_user(user)
        import httpx
        h = {"Authorization": f"Bearer {pair.access_token}"}

        def check(label, cond):
            print(("PASS" if cond else "FAIL"), label)
            if not cond:
                sys.exit(1)

        with httpx.Client(base_url=BASE, headers=h, timeout=15, follow_redirects=True) as c:
            def raw(label, method, path, **kw):
                try:
                    r = getattr(c, method)(path, **kw)
                except Exception as exc:
                    print(f"[{label}] EXC {type(exc).__name__}: {exc}")
                    return None
                print(f"[{label}] {method.upper()} {path} status={r.status_code} loc={r.headers.get('location')!r} len={len(r.text)}")
                if r.status_code >= 300:
                    print("   body=", r.text[:200])
                    return None
                try:
                    return r.json()
                except Exception:
                    print("   NON_JSON body=", r.text[:200])
                    return None

            body = raw("get-config", "get", "")
            check("GET config 200", body is not None and body.get("max_free") == 3)
            check("bowlfuel blocked", bool(body) and any("bowlfuel.com" in d for d in body["blocked"]))
            orig_blocked = body["blocked"] if body else []

            b = raw("accounts", "get", "/accounts", params={"domain": "bowlfuel.com"})
            check("accounts bowlfuel 2", b is not None and b.get("count") == 2)

            r = raw("block", "post", "/domain-action", json={"domain": "sgprobe.invalid", "action": "block"})
            check("action block 200", r is not None and r.get("blocked_count", 0) >= len(orig_blocked))

            b2 = raw("get-config-2", "get", "")
            check("sgprobe.invalid blocked", b2 is not None and "sgprobe.invalid" in b2["blocked"])

            r = raw("suspend", "post", "/domain-action", json={"domain": "no.suchdomain.invalid", "action": "suspend"})
            check("suspend no-op 0", r is not None and r.get("affected_accounts") == 0)

            r = raw("freeze", "post", "/domain-action", json={"domain": "no.suchdomain.invalid", "action": "freeze", "hours": 24})
            check("freeze no-op 0", r is not None and r.get("affected_accounts") == 0)

            r = raw("reactivate", "post", "/domain-action", json={"domain": "no.suchdomain.invalid", "action": "reactivate"})
            check("reactivate no-op 0", r is not None and r.get("affected_accounts") == 0)

            r = raw("unblock", "post", "/domain-action", json={"domain": "sgprobe.invalid", "action": "unblock"})
            check("action unblock 200", r is not None)

            b3 = raw("restore", "put", "", json={"blocked": orig_blocked})
            check("restored blocked list", b3 is not None and b3.get("blocked") == orig_blocked)

        print("ADMIN_SG_FULL_VERIFY_OK")
    finally:
        clear_connections()
        await redis_conn.aclose()
        await pool.close()


asyncio.run(main())
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
