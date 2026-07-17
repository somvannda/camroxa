#!/usr/bin/env python3
"""Reproduce audit-log error on sandbox."""

from __future__ import annotations

import json
import sys
import urllib.error
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / ".venv" / "Lib" / "site-packages"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from deploy import ensure_deploy_key, load_secrets, ssh_connect  # noqa: E402

REMOTE = r"""
import asyncio, json, os, asyncpg, traceback

async def main():
    dsn = os.environ['PLATFORM_DATABASE_URL'].replace('postgresql+asyncpg://', 'postgresql://', 1)
    conn = await asyncpg.connect(dsn)
    try:
        cols = await conn.fetch(
            "SELECT column_name FROM information_schema.columns WHERE table_name='audit_logs' ORDER BY ordinal_position"
        )
        print('audit_logs columns:', [r['column_name'] for r in cols])
        total = await conn.fetchval('SELECT COUNT(*) FROM audit_logs')
        print('audit_logs count:', total)
        row = await conn.fetchrow(
            '''SELECT id, actor_id, action_type, target_resource, outcome,
                      credit_impact, source_ip, client_id, endpoint_path, metadata, created_at
               FROM audit_logs ORDER BY created_at DESC LIMIT 1'''
        )
        print('sample row:', dict(row) if row else None)
    except Exception:
        traceback.print_exc()
    finally:
        await conn.close()

    # exercise audit repo query like API
    try:
        from platform_api.repositories.audit_repo import AuditRepository, AuditQueryFilters
        pool = await asyncpg.create_pool(dsn, min_size=1, max_size=1)
        repo = AuditRepository(pool)
        result = await repo.query(page=1, page_size=50)
        print('repo query ok:', result.total, 'entries', len(result.entries))
        if result.entries:
            e = result.entries[0]
            print('first entry actor:', e.actor_id, 'meta type:', type(e.metadata))
        await pool.close()
    except Exception:
        traceback.print_exc()

asyncio.run(main())
"""


def https_json(method: str, url: str, data: dict | None = None, token: str | None = None):
    body = None if data is None else json.dumps(data).encode()
    headers = {"Content-Type": "application/json", "X-Portal-Context": "admin"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return resp.status, resp.read().decode()
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read().decode()


def main() -> int:
    login_status, login_body = https_json(
        "POST",
        "https://api.sandbox.camxora.com/api/v1/auth/login",
        {"email": "duke@camxora.com", "password": "Iamduke168!!@@##$$"},
    )
    print("login:", login_status, login_body[:200])
    token = json.loads(login_body).get("access_token") if login_status == 200 else None

    if token:
        status, body = https_json(
            "GET",
            "https://api.sandbox.camxora.com/api/v1/admin/audit-log?page=1&page_size=50",
            token=token,
        )
        print("audit-log:", status, body[:500])

    client = ssh_connect(
        load_secrets()["VPS_HOST"],
        load_secrets()["VPS_USER"],
        ensure_deploy_key(),
        None,
    )
    remote_py = "/tmp/camxora_audit_diag.py"
    sftp = client.open_sftp()
    with sftp.file(remote_py, "w") as fh:
        fh.write(REMOTE)
    sftp.close()
    cmd = (
        f"sudo -u camxora bash -lc 'cd /opt/camxora/repo && set -a && source platform_api/.env && set +a && "
        f"platform_api/.venv/bin/python {remote_py}'"
    )
    _, stdout, stderr = client.exec_command(cmd)
    print(stdout.read().decode("utf-8", errors="replace"))
    err = stderr.read().decode("utf-8", errors="replace")
    if err.strip():
        print("STDERR:", err)
    client.exec_command(f"journalctl -u camxora-api -n 15 --no-pager")
    _, out2, _ = client.exec_command("journalctl -u camxora-api -n 15 --no-pager")
    print(out2.read().decode("utf-8", errors="replace"))
    client.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
