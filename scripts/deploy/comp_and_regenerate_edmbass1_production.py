#!/usr/bin/env python3
"""Production: comp 7.5 credits to edmbass1 and regenerate the lost track.

Steps:
  1. add_credits(75_000 units = 7.5 credits) to the user's wallet (comp).
  2. Retire the old (lost) task's request_hash so submit_suno's dedup does not
     return it and a genuinely new generation is created.
  3. POST /api/v1/batches/{batch}/songs/{song}/retry-suno with a user JWT.
  4. Poll for the new suno task.

Dry-run by default; pass --apply. Refuses non-production hosts.
"""
from __future__ import annotations

import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DEPLOY = ROOT / "scripts" / "deploy"
sys.path.insert(0, str(DEPLOY / ".venv" / "Lib" / "site-packages"))
sys.path.insert(0, str(DEPLOY))

from deploy import (  # noqa: E402
    CANONICAL_PRODUCTION_HOST,
    CANONICAL_SANDBOX_HOST,
    ensure_deploy_key,
    load_production_secrets,
    resolve_production_ssh,
    ssh_connect,
)

PRODUCTION_HOST = "82.197.71.248"
BATCH_ID = "28125ad7-beda-4dcc-b052-e2a7bbcbeffe"
SONG_ID = "e2a17144-6731-4570-8aa8-faa946c2fbc0"
USER_ID = "ad6eda59-18f0-4ffb-b80e-fdae60028980"
OLD_TASK_ID = "4cef5b17-c7d5-4fec-bff4-72d7bae68671"
GRANT_UNITS = 75000

REMOTE_PY = r'''
import asyncio
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import UUID

os.chdir("/opt/camxora/repo")
sys.path.insert(0, "/opt/camxora/repo")
env_path = Path("/opt/camxora/repo/platform_api/.env")
if env_path.is_file():
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip().strip("\"'"))

import asyncpg
import httpx
import jwt
from platform_api.config import get_settings
from platform_api.repositories.credit_repo import CreditRepository

APPLY = os.environ.get("CX_APPLY") == "1"
BATCH_ID = os.environ["CX_BATCH_ID"]
SONG_ID = os.environ["CX_SONG_ID"]
USER_ID = os.environ["CX_USER_ID"]
OLD_TASK_ID = os.environ["CX_OLD_TASK_ID"]
GRANT_UNITS = int(os.environ["CX_GRANT_UNITS"])
BASE = "http://127.0.0.1:8100"
ROUTE = f"/api/v1/batches/{BATCH_ID}/songs/{SONG_ID}/retry-suno"


async def main() -> int:
    settings = get_settings()
    dsn = settings.database_url.replace("postgresql+asyncpg://", "postgresql://")
    pool = await asyncpg.create_pool(dsn, min_size=1, max_size=2)
    try:
        bal_before = await pool.fetchval("SELECT balance FROM credit_wallets WHERE user_id=$1", UUID(USER_ID))
        old_hash = await pool.fetchval("SELECT request_hash FROM suno_tasks WHERE id=$1", UUID(OLD_TASK_ID))
        print("BEFORE balance_units=", bal_before, "old_hash=", old_hash)

        if not APPLY:
            print("DRY_RUN: would grant", GRANT_UNITS, "units and retire old hash, then POST", ROUTE)
            return 0

        # 1. comp credits (idempotent: only top up to the needed amount)
        if bal_before is None or int(bal_before) < GRANT_UNITS:
            new_balance = await CreditRepository(pool).add_credits(
                UUID(USER_ID),
                GRANT_UNITS - int(bal_before or 0),
                "comp_lost_audio_regen",
                ref_id=f"lost-audio-regen:{SONG_ID}",
            )
            print("GRANTED units=", GRANT_UNITS, "new_balance_units=", new_balance)
        else:
            print("GRANT_SKIPPED balance_units=", bal_before)

        # 2. retire old task hash so dedup creates a new task (column is varchar(64))
        import secrets

        await pool.execute(
            "UPDATE suno_tasks SET request_hash = $2 WHERE id=$1",
            UUID(OLD_TASK_ID),
            secrets.token_hex(32),
        )
        print("OLD_HASH_RETIRED")

        # 3. trigger retry-suno
        user = await pool.fetchrow(
            "SELECT id, email, role, COALESCE(token_version,0) AS token_version FROM users WHERE id=$1",
            UUID(USER_ID),
        )
        now = datetime.now(timezone.utc)
        token = jwt.encode(
            {
                "user_id": str(user["id"]),
                "email": user["email"],
                "role": str(user["role"] or "user"),
                "token_version": int(user["token_version"] or 0),
                "exp": now + timedelta(minutes=10),
                "iat": now,
                "type": "access",
            },
            settings.jwt_secret,
            algorithm=settings.jwt_algorithm,
        )
        if isinstance(token, bytes):
            token = token.decode("ascii")
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                f"{BASE}{ROUTE}",
                headers={"Authorization": f"Bearer {token}"},
                json={},
            )
            print("POST", resp.status_code, resp.text[:400])

        # 4. poll for a new task
        for i in range(12):
            tasks = await pool.fetch(
                "SELECT id, status, external_task_id, created_at FROM suno_tasks WHERE song_id=$1 ORDER BY created_at DESC LIMIT 3",
                UUID(SONG_ID),
            )
            print("poll", i, [{k: str(v) for k, v in dict(t).items()} for t in tasks])
            newest = tasks[0] if tasks else None
            if newest and str(newest["id"]) != OLD_TASK_ID and str(newest["status"]).lower() not in {"pending"}:
                break
            if newest and str(newest["id"]) != OLD_TASK_ID:
                break
            await asyncio.sleep(6)

        bal_after = await pool.fetchval("SELECT balance FROM credit_wallets WHERE user_id=$1", UUID(USER_ID))
        print("AFTER balance_units=", bal_after)
    finally:
        await pool.close()
    print("REGEN_DONE")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
'''


def main() -> int:
    apply = "--apply" in sys.argv
    secrets = load_production_secrets()
    host, user, password = resolve_production_ssh(secrets)
    if host != CANONICAL_PRODUCTION_HOST or host == CANONICAL_SANDBOX_HOST:
        raise SystemExit(f"Refusing non-production host: {host}")
    print(f"=== comp + regenerate edmbass1 [{'APPLY' if apply else 'DRY-RUN'}] {host} ===")
    client = ssh_connect(host, user, ensure_deploy_key(), password)
    try:
        remote = "/opt/camxora/tmp/comp_and_regenerate_edmbass1.py"
        with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False, encoding="utf-8") as tmp:
            tmp.write(REMOTE_PY)
            local_py = tmp.name
        sftp = client.open_sftp()
        sftp.put(local_py, remote)
        sftp.close()
        Path(local_py).unlink(missing_ok=True)
        env = (
            f"CX_APPLY={'1' if apply else '0'} CX_BATCH_ID={BATCH_ID} CX_SONG_ID={SONG_ID} "
            f"CX_USER_ID={USER_ID} CX_OLD_TASK_ID={OLD_TASK_ID} CX_GRANT_UNITS={GRANT_UNITS}"
        )
        cmd = (
            "set -e\n"
            "chown camxora:camxora " + remote + "\n"
            "sudo -u camxora bash -lc 'cd /opt/camxora/repo && "
            "PYTHONPATH=/opt/camxora/repo PYTHONUNBUFFERED=1 " + env + " "
            "/opt/camxora/repo/platform_api/.venv/bin/python -u " + remote + "'\n"
            "rm -f " + remote + "\n"
        )
        _, stdout, stderr = client.exec_command(cmd, get_pty=False, timeout=300)
        out = stdout.read().decode("utf-8", errors="replace")
        err = stderr.read().decode("utf-8", errors="replace")
        sys.stdout.buffer.write(out.encode("utf-8", errors="replace"))
        if err.strip():
            sys.stderr.write(err[-3000:] + "\n")
        return stdout.channel.return_exit_status() if hasattr(stdout.channel, "return_exit_status") else stdout.channel.recv_exit_status()
    finally:
        client.close()


if __name__ == "__main__":
    raise SystemExit(main())
