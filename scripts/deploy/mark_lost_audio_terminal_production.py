#!/usr/bin/env python3
"""Production: mark a dead upload job permanent + its task channel as lost (terminal).

Does two things for one mp3 job:
  1. stream_upload_jobs.permanent_failed = true (stops retrying the archive upload)
  2. suno_tasks.download_unavailable_<variant> = true (marks the track lost; this is
     the flag the pipeline/regeneration path reads — NOT permanent_failed).

Note: by design this does NOT make the album export at N-1 tracks. The video
pipeline waits for a real resolution (recovery or regeneration) of the lost track.

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

REMOTE_PY = r'''
import asyncio
import os
import sys
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
from platform_api.config import get_settings, is_production

APPLY = os.environ.get("CX_APPLY") == "1"
JOB_ID = os.environ["CX_JOB_ID"]
TASK_ID = os.environ["CX_TASK_ID"]
VARIANT = os.environ.get("CX_VARIANT", "ok").strip().lower()
if VARIANT not in {"ok", "alt"}:
    raise SystemExit("variant must be ok or alt")


async def show(pool, label):
    job = await pool.fetchrow(
        "SELECT id, kind, status, permanent_failed, attempt_count FROM stream_upload_jobs WHERE id=$1",
        JOB_ID,
    )
    task = await pool.fetchrow(
        "SELECT id, status, source, downloaded_ok, downloaded_alt, "
        "download_unavailable_ok, download_unavailable_alt FROM suno_tasks WHERE id=$1",
        TASK_ID,
    )
    print(label, "JOB", dict(job) if job else None)
    print(label, "TASK", dict(task) if task else None)


async def main() -> int:
    settings = get_settings()
    if not is_production(settings):
        print("REFUSE: not production")
        return 2
    dsn = settings.database_url.replace("postgresql+asyncpg://", "postgresql://")
    pool = await asyncpg.create_pool(dsn, min_size=1, max_size=2)
    try:
        await show(pool, "BEFORE")
        if APPLY:
            j = await pool.execute(
                """
                UPDATE stream_upload_jobs
                SET permanent_failed = true,
                    status = 'failed',
                    error = COALESCE(error, 'Permanently failed: Suno audio gone, no B2 copy.'),
                    updated_at = NOW()
                WHERE id = $1
                """,
                JOB_ID,
            )
            print("MARKED_JOB", j)
            t = await pool.execute(
                f"""
                UPDATE suno_tasks
                SET download_unavailable_{VARIANT} = true,
                    download_unavailable_at_{VARIANT} = NOW(),
                    updated_at = NOW()
                WHERE id = $1
                """,
                TASK_ID,
            )
            print("MARKED_TASK_LOST", t)
        await show(pool, "AFTER")
    finally:
        await pool.close()
    print("LOST_AUDIO_TERMINAL_DONE")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
'''

JOB_ID = "5abef4fd-3d10-4802-b6ab-72934ce7ba7c"
TASK_ID = "4cef5b17-c7d5-4fec-bff4-72d7bae68671"
VARIANT = "ok"


def main() -> int:
    apply = "--apply" in sys.argv
    secrets = load_production_secrets()
    host, user, password = resolve_production_ssh(secrets)
    if host != CANONICAL_PRODUCTION_HOST or host == CANONICAL_SANDBOX_HOST:
        raise SystemExit(f"Refusing non-production host: {host}")
    print(f"=== mark lost audio terminal [{'APPLY' if apply else 'DRY-RUN'}] {host} ===")
    client = ssh_connect(host, user, ensure_deploy_key(), password)
    try:
        remote = "/opt/camxora/tmp/mark_lost_audio_terminal.py"
        with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False, encoding="utf-8") as tmp:
            tmp.write(REMOTE_PY)
            local_py = tmp.name
        sftp = client.open_sftp()
        sftp.put(local_py, remote)
        sftp.close()
        Path(local_py).unlink(missing_ok=True)
        env = (
            f"CX_APPLY={'1' if apply else '0'} CX_JOB_ID={JOB_ID} "
            f"CX_TASK_ID={TASK_ID} CX_VARIANT={VARIANT}"
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
            sys.stderr.write(err[-2000:] + "\n")
        return stdout.channel.recv_exit_status()
    finally:
        client.close()


if __name__ == "__main__":
    raise SystemExit(main())
