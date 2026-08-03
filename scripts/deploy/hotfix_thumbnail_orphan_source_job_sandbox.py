#!/usr/bin/env python3
"""File-scoped sandbox hotfix: album thumbnail source_job_id race remap only."""

from __future__ import annotations

import os
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
FILE_REPO = Path(os.environ.get("CAMXORA_HOTFIX_REPO") or SCRIPT_DIR.parents[1])
# Secrets / paramiko venv often live on the primary checkout, not a worktree.
_PRIMARY = Path(r"D:\Development\Projects\Electron\MusicGenerator")
_DEPLOY_CANDIDATES = [_PRIMARY / "scripts" / "deploy", SCRIPT_DIR]
for candidate in _DEPLOY_CANDIDATES:
    venv_site = candidate / ".venv" / "Lib" / "site-packages"
    if venv_site.is_dir():
        sys.path.insert(0, str(venv_site))
    if (candidate / "deploy.py").is_file():
        sys.path.insert(0, str(candidate))
        break

from deploy import ensure_deploy_key, load_sandbox_secrets, resolve_sandbox_ssh, ssh_connect  # noqa: E402

FILES = [
    "platform_api/repositories/batch_repo.py",
]

ORPHAN_THUMB = "354f25f9-58d6-4483-87fb-9cef950fe581"
ALT_BG = "4572a037-1e53-4b70-b273-f15c57352e1e"

REPAIR_REMOTE = f"""
import asyncio
import os

import asyncpg

ORPHAN = "{ORPHAN_THUMB}"
BG = "{ALT_BG}"

async def main():
    dsn = os.environ["PLATFORM_DATABASE_URL"].replace("postgresql+asyncpg://", "postgresql://", 1)
    conn = await asyncpg.connect(dsn)
    row = await conn.fetchrow(
        "SELECT id, status, source_job_id, attempt_count FROM image_jobs WHERE id = $1::uuid",
        ORPHAN,
    )
    print("BEFORE", dict(row) if row else None)
    if row and row["status"] == "failed":
        await conn.execute(
            "UPDATE image_jobs SET source_job_id = $1::uuid, status = 'pending', "
            "attempt_count = 0, error = '', updated_at = NOW() WHERE id = $2::uuid",
            BG,
            ORPHAN,
        )
        after = await conn.fetchrow(
            "SELECT id, status, source_job_id, attempt_count, error FROM image_jobs WHERE id = $1::uuid",
            ORPHAN,
        )
        print("AFTER", dict(after) if after else None)
    await conn.close()

asyncio.run(main())
"""


def _run(client, cmd: str, timeout: int = 120) -> tuple[int, str]:
    _, stdout, stderr = client.exec_command(cmd, get_pty=True, timeout=timeout)
    out = stdout.read().decode("utf-8", errors="replace")
    err = stderr.read().decode("utf-8", errors="replace")
    code = stdout.channel.recv_exit_status()
    return code, (out + ("\n" + err if err.strip() else "")).strip()


def main() -> int:
    secrets = load_sandbox_secrets()
    host, user, password = resolve_sandbox_ssh(secrets)
    print(f"Target sandbox host: {host}")
    print(f"File source repo: {FILE_REPO}")
    client = ssh_connect(host, user, ensure_deploy_key(), password)
    try:
        sftp = client.open_sftp()
        for rel in FILES:
            local = FILE_REPO / rel
            if not local.is_file():
                raise FileNotFoundError(local)
            remote = f"/opt/camxora/repo/{rel}"
            print(f"Uploading {rel} ...")
            sftp.put(str(local), remote)
        sftp.close()

        code, out = _run(
            client,
            "chown camxora:camxora /opt/camxora/repo/platform_api/repositories/batch_repo.py"
            " && grep -n background_id_remap /opt/camxora/repo/platform_api/repositories/batch_repo.py | head -3"
            " && systemctl restart camxora-api && sleep 2 && systemctl is-active camxora-api"
            " && echo API_HOTFIX_OK",
            timeout=60,
        )
        print(out)
        if code != 0:
            return code

        sftp = client.open_sftp()
        with sftp.open("/tmp/_repair_orphan_thumb.py", "w") as remote:
            remote.write(REPAIR_REMOTE)
        sftp.close()
        code, out = _run(
            client,
            "sudo -u camxora bash -lc "
            "'cd /opt/camxora/repo/platform_api && set -a && source .env && set +a && "
            ".venv/bin/python /tmp/_repair_orphan_thumb.py'",
            timeout=60,
        )
        print(out)
        print("SANDBOX_THUMB_ORPHAN_HOTFIX_DONE")
        return code
    finally:
        client.close()


if __name__ == "__main__":
    raise SystemExit(main())
