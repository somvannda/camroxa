#!/usr/bin/env python3
"""Production: trigger retry-suno for edmbass1's lost song via the real API.

Generates a short-lived access token for the batch owner, POSTs
/batches/{batch}/songs/{song}/retry-suno on the local API, then reports the
enqueued job. Pass --apply (dry-run shows the resolved route only).
"""
from __future__ import annotations

import sys
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

REMOTE_PY = r'''
import asyncio
import json
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

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

APPLY = os.environ.get("CX_APPLY") == "1"
BATCH_ID = os.environ["CX_BATCH_ID"]
SONG_ID = os.environ["CX_SONG_ID"]
USER_ID = os.environ["CX_USER_ID"]

BASE = "http://127.0.0.1:8100"


async def main() -> int:
    settings = get_settings()
    dsn = settings.database_url.replace("postgresql+asyncpg://", "postgresql://")
    pool = await asyncpg.create_pool(dsn, min_size=1, max_size=2)
    try:
        user = await pool.fetchrow(
            "SELECT id, email, role, COALESCE(token_version,0) AS token_version FROM users WHERE id=$1",
            USER_ID,
        )
        if not user:
            print("NO_USER"); return 2
        print("USER", dict(user))

        async with httpx.AsyncClient(timeout=30.0) as client:
            all_paths: list[str] = []
            for spec_url in (
                "/api/v3/openapi.json",
                "/api/v1/openapi.json",
                "/api/v2/openapi.json",
                "/openapi.json",
            ):
                try:
                    r = await client.get(f"{BASE}{spec_url}")
                    if r.status_code != 200:
                        continue
                    sp = r.json()
                    paths = list(sp.get("paths", {}))
                    print("SPEC", spec_url, "paths", len(paths))
                    if paths:
                        all_paths = paths
                        break
                except Exception as exc:
                    print("SPEC_ERR", spec_url, str(exc)[:120])
            print("SAMPLE_PATHS", all_paths[:30])
            paths = [p for p in all_paths if "retry-suno" in p]
            print("ROUTES", paths)
            if not paths:
                print("NO_RETRY_SUno_ROUTE"); return 2
            route = paths[0].replace("{batch_id}", BATCH_ID).replace("{song_id}", SONG_ID)

            if not APPLY:
                print("DRY_RUN route", route)
                return 0

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

            resp = await client.post(
                f"{BASE}{route}",
                headers={"Authorization": f"Bearer {token}"},
                json={},
            )
            print("POST", resp.status_code, resp.text[:600])

        jobs = await pool.fetch(
            """
            SELECT id, job_type, status, song_id, created_at
            FROM job_queue
            WHERE song_id = $1 AND job_type ILIKE '%suno%'
            ORDER BY created_at DESC LIMIT 5
            """,
            SONG_ID,
        )
        print("JOBS", [dict(j) for j in jobs])

        tasks = await pool.fetch(
            """
            SELECT id, status, external_task_id, created_at
            FROM suno_tasks WHERE song_id = $1
            ORDER BY created_at DESC LIMIT 5
            """,
            SONG_ID,
        )
        print("TASKS", [{k: str(v) for k, v in dict(t).items()} for t in tasks])
    finally:
        await pool.close()
    print("TRIGGER_DONE")
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
    print(f"=== trigger retry-suno [{'APPLY' if apply else 'DRY-RUN'}] {host} ===")
    client = ssh_connect(host, user, ensure_deploy_key(), password)
    try:
        remote = "/opt/camxora/tmp/trigger_retry_suno.py"
        with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False, encoding="utf-8") as tmp:
            tmp.write(REMOTE_PY)
            local_py = tmp.name
        sftp = client.open_sftp()
        sftp.put(local_py, remote)
        sftp.close()
        Path(local_py).unlink(missing_ok=True)
        env = (
            f"CX_APPLY={'1' if apply else '0'} CX_BATCH_ID={BATCH_ID} "
            f"CX_SONG_ID={SONG_ID} CX_USER_ID={USER_ID}"
        )
        cmd = (
            "set -e\n"
            "chown camxora:camxora " + remote + "\n"
            "sudo -u camxora bash -lc 'cd /opt/camxora/repo && "
            "PYTHONPATH=/opt/camxora/repo PYTHONUNBUFFERED=1 " + env + " "
            "/opt/camxora/repo/platform_api/.venv/bin/python -u " + remote + "'\n"
            "rm -f " + remote + "\n"
        )
        _, stdout, stderr = client.exec_command(cmd, get_pty=False, timeout=180)
        out = stdout.read().decode("utf-8", errors="replace")
        err = stderr.read().decode("utf-8", errors="replace")
        sys.stdout.buffer.write(out.encode("utf-8", errors="replace"))
        if err.strip():
            sys.stderr.write(err[-2500:] + "\n")
        return stdout.channel.recv_exit_status()
    finally:
        client.close()


if __name__ == "__main__":
    import tempfile

    raise SystemExit(main())
