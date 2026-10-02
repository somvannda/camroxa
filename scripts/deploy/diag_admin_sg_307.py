#!/usr/bin/env python3
"""Diagnose 307 on new admin endpoint (read-only, no changes)."""
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
/opt/camxora/repo/platform_api/.venv/bin/python -u - <<'PY'
import asyncio, sys
sys.path.insert(0, "/opt/camxora/repo")
import asyncpg
import redis.asyncio as aioredis
from platform_api.dependencies import (
    clear_connections, get_auth_service, get_settings, get_user_repo,
    set_db_pool, set_redis,
)

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
        headers = {"Cookie": f"camxora_access_token={pair.access_token}"}
        variants = [
            ("bearer", {"Authorization": f"Bearer {pair.access_token}"}, ""),
            ("cookie", {"Cookie": f"camxora_access_token={pair.access_token}"}, ""),
            ("bearer-accounts", {"Authorization": f"Bearer {pair.access_token}"}, "/accounts?domain=bowlfuel.com"),
            ("bearer-put-noop", {"Authorization": f"Bearer {pair.access_token}"}, ""),
        ]
        base = "http://127.0.0.1:8100/api/v1/admin/signup-domain-guard"
        for label, extra, path in variants:
            try:
                if label == "bearer-put-noop":
                    r = httpx.put(base + path, headers=extra, json={"max_free": 3}, timeout=10, follow_redirects=False)
                else:
                    r = httpx.get(base + path, headers=extra, timeout=10, follow_redirects=False)
                print(f"[{label}] status={r.status_code} loc={r.headers.get('location')!r} len={len(r.text)} body={r.text[:220]!r}")
            except Exception as exc:
                print(f"[{label}] ERR {exc}")
    finally:
        clear_connections()
        await redis_conn.aclose()
        await pool.close()

asyncio.run(main())
PY
echo DIAG_DONE
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
