#!/usr/bin/env python3
"""Production: revert permanent-failed mp3 upload jobs and retry the missing ones.

Split (not a blanket reset):
  A. permanent_failed jobs that ALREADY have a B2 copy -> status='success'
     (they are effectively done; retrying would needlessly re-download).
  B. permanent_failed jobs with NO B2 copy -> clear permanent_failed,
     reset attempt_count=0, status='failed' so they are retryable.
Then, with --retry, run StreamingUploadService.retry_failed_job on every
non-permanent failed/pending mp3 job that still lacks a B2 copy. That path uses
the provider Recovery-Audio fallback, so expired temp URLs can still be re-minted.

Dry-run by default. Pass --apply to write, and --retry to run the retries.
Refuses non-production hosts. Host must be 82.197.71.248.
"""
from __future__ import annotations

import json
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
import json
import os
import sys
from pathlib import Path

os.chdir("/opt/camxora/repo")
sys.path.insert(0, "/opt/camxora/repo")
try:
    sys.stdout.reconfigure(line_buffering=True)
except Exception:
    pass
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
from platform_api.services.streaming_upload_service import StreamingUploadService

APPLY = os.environ.get("CX_APPLY") == "1"
RETRY = os.environ.get("CX_RETRY") == "1"
SNAPSHOT_PATH = "/opt/camxora/tmp/permanent_upload_jobs_snapshot.json"

HAS_B2 = """
EXISTS (
  SELECT 1 FROM stream_tracks t
  WHERE t.suno_task_id = j.suno_task_id
    AND t.variant = CASE WHEN j.kind = 'mp3_ok' THEN 'ok' ELSE 'alt' END
    AND COALESCE(t.storage_key, '') <> ''
)
"""


async def counts(pool) -> dict:
    row = await pool.fetchrow(
        """
        SELECT
          count(*) FILTER (WHERE COALESCE(j.permanent_failed,false)) permanent,
          count(*) FILTER (WHERE COALESCE(j.permanent_failed,false) AND {has_b2}) permanent_with_b2,
          count(*) FILTER (WHERE COALESCE(j.permanent_failed,false) AND NOT {has_b2}) permanent_no_b2,
          count(*) FILTER (WHERE COALESCE(j.permanent_failed,false)=false
                             AND j.status IN ('failed','pending') AND NOT {has_b2}) retryable_no_b2
        FROM stream_upload_jobs j
        WHERE j.kind IN ('mp3_ok','mp3_alt')
        """.format(has_b2=HAS_B2)
    )
    return dict(row)


async def main() -> int:
    settings = get_settings()
    if not is_production(settings):
        print("REFUSE: not production")
        return 2
    dsn = settings.database_url.replace("postgresql+asyncpg://", "postgresql://")
    pool = await asyncpg.create_pool(dsn, min_size=1, max_size=3)
    try:
        before = await counts(pool)
        print("BEFORE", json.dumps(before))

        # Snapshot the rows we are about to change (for rollback).
        snapshot = await pool.fetch(
            """
            SELECT j.id, j.status, j.permanent_failed, j.attempt_count, j.error
            FROM stream_upload_jobs j
            WHERE j.kind IN ('mp3_ok','mp3_alt') AND COALESCE(j.permanent_failed,false)=true
            """
        )
        Path(SNAPSHOT_PATH).write_text(
            json.dumps([dict(r) for r in snapshot], default=str),
            encoding="utf-8",
        )
        print("SNAPSHOT_COUNT", len(snapshot), SNAPSHOT_PATH)

        if APPLY:
            reconciled = await pool.execute(
                """
                UPDATE stream_upload_jobs j
                SET permanent_failed = false,
                    status = 'success',
                    updated_at = NOW()
                WHERE j.kind IN ('mp3_ok','mp3_alt')
                  AND COALESCE(j.permanent_failed,false) = true
                  AND {has_b2}
                """.format(has_b2=HAS_B2)
            )
            print("RECONCILED_WITH_B2", reconciled)

            unmarked = await pool.execute(
                """
                UPDATE stream_upload_jobs j
                SET permanent_failed = false,
                    attempt_count = 0,
                    status = 'failed',
                    error = NULL,
                    updated_at = NOW()
                WHERE j.kind IN ('mp3_ok','mp3_alt')
                  AND COALESCE(j.permanent_failed,false) = true
                  AND NOT {has_b2}
                """.format(has_b2=HAS_B2)
            )
            print("UNMARKED_NO_B2", unmarked)

            cleared = await pool.execute(
                """
                UPDATE suno_tasks st
                SET download_unavailable_ok = false,
                    download_unavailable_alt = false,
                    updated_at = NOW()
                WHERE COALESCE(st.download_unavailable_ok,false) = true
                   OR COALESCE(st.download_unavailable_alt,false) = true
                """
            )
            print("CLEARED_DOWNLOAD_UNAVAILABLE", cleared)

        after = await counts(pool)
        print("AFTER", json.dumps(after))

        if RETRY:
            rows = await pool.fetch(
                """
                SELECT j.id
                FROM stream_upload_jobs j
                WHERE j.kind IN ('mp3_ok','mp3_alt')
                  AND COALESCE(j.permanent_failed,false) = false
                  AND j.status IN ('failed','pending')
                  AND NOT {has_b2}
                ORDER BY j.created_at DESC
                """.format(has_b2=HAS_B2)
            )
            service = StreamingUploadService(pool)
            ok = fail = 0
            errors = []
            for row in rows:
                job_id = row["id"]
                try:
                    await service.retry_failed_job(job_id)
                    ok += 1
                    print(f"RETRY_OK {job_id}")
                except Exception as exc:
                    fail += 1
                    msg = str(exc)[:220] or exc.__class__.__name__
                    errors.append({"job_id": str(job_id), "error": msg})
                    print(f"RETRY_FAIL {job_id} {msg}")
            print("RETRY_SUMMARY", json.dumps({"total": len(rows), "ok": ok, "failed": fail}))
            print("RETRY_ERRORS " + json.dumps(errors))

        final = await counts(pool)
        print("FINAL", json.dumps(final))
    finally:
        await pool.close()
    print("PERMANENT_REVERT_DONE")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
'''


def _run(client, apply: bool, retry: bool, timeout: int) -> int:
    import time

    remote = "/opt/camxora/tmp/revert_upload_job_permanent_failed.py"
    with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False, encoding="utf-8") as tmp:
        tmp.write(REMOTE_PY)
        local_py = tmp.name
    sftp = client.open_sftp()
    sftp.put(local_py, remote)
    sftp.close()
    Path(local_py).unlink(missing_ok=True)
    env = f"CX_APPLY={'1' if apply else '0'} CX_RETRY={'1' if retry else '0'}"
    cmd = (
        "set -e\n"
        "chown camxora:camxora " + remote + "\n"
        "sudo -u camxora bash -lc 'cd /opt/camxora/repo && "
        "PYTHONPATH=/opt/camxora/repo PYTHONUNBUFFERED=1 " + env + " "
        "/opt/camxora/repo/platform_api/.venv/bin/python -u " + remote + "'\n"
        "rm -f " + remote + "\n"
    )
    _, stdout, stderr = client.exec_command(cmd, get_pty=False, timeout=timeout)
    out = stdout.read().decode("utf-8", errors="replace")
    err = stderr.read().decode("utf-8", errors="replace")
    code = stdout.channel.recv_exit_status()
    sys.stdout.buffer.write(out.encode("utf-8", errors="replace"))
    if err.strip():
        sys.stderr.write(err[-4000:] + "\n")
    if apply:
        local_snap = Path(tempfile.gettempdir()) / "permanent_upload_jobs_snapshot.json"
        try:
            sftp = client.open_sftp()
            sftp.get("/opt/camxora/tmp/permanent_upload_jobs_snapshot.json", str(local_snap))
            sftp.close()
            print(f"Snapshot saved locally: {local_snap}")
        except Exception as exc:
            print(f"WARNING: could not pull snapshot: {exc}")
    return code


def main() -> int:
    apply = "--apply" in sys.argv
    retry = "--retry" in sys.argv
    secrets = load_production_secrets()
    host, user, password = resolve_production_ssh(secrets)
    if host != CANONICAL_PRODUCTION_HOST or host == CANONICAL_SANDBOX_HOST:
        raise SystemExit(f"Refusing non-production host: {host}")
    mode = "APPLY" if apply else "DRY-RUN"
    print(f"=== revert permanent-failed upload jobs [{mode}{' + RETRY' if retry else ''}] {host} ===")
    client = ssh_connect(host, user, ensure_deploy_key(), password)
    try:
        return _run(client, apply=apply, retry=retry, timeout=2400)
    finally:
        client.close()


if __name__ == "__main__":
    raise SystemExit(main())
