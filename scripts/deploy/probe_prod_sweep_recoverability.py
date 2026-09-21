#!/usr/bin/env python3
"""READ-ONLY: failed-mp3 recoverability probe (suno task context availability by age)."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DEPLOY = ROOT / "scripts" / "deploy"
sys.path.insert(0, str(DEPLOY / ".venv" / "Lib" / "site-packages"))
sys.path.insert(0, str(DEPLOY))

from deploy import ensure_deploy_key, load_production_secrets, resolve_production_ssh, ssh_connect  # noqa: E402

PRODUCTION_HOST = "82.197.71.248"
PSQL = "sudo -u postgres psql -d camxora_platform -P pager=off -t -A"

QUERIES = r'''
echo "=== A. failed mp3 by month: total / with suno_task / with suno_tasks row ==="
%PSQL% -c "SELECT to_char(j.created_at,'YYYY-MM') AS month, count(*) AS n, count(j.suno_task_id) AS with_suno_task, count(st.id) AS with_context FROM stream_upload_jobs j LEFT JOIN suno_tasks st ON st.id = j.suno_task_id WHERE j.status='failed' AND j.kind IN ('mp3_ok','mp3_alt') GROUP BY 1 ORDER BY 1;"

echo "=== B. failed mp3 missing suno_task_id ==="
%PSQL% -c "SELECT 'missing_suno_task=' || count(*) FROM stream_upload_jobs WHERE status='failed' AND kind IN ('mp3_ok','mp3_alt') AND suno_task_id IS NULL;"

echo "=== C. source host histogram (failed mp3) ==="
%PSQL% -c "SELECT split_part(split_part(source_url,'/',3),':',1) AS host, count(*) AS n FROM stream_upload_jobs WHERE status='failed' AND kind IN ('mp3_ok','mp3_alt') GROUP BY 1 ORDER BY 2 DESC LIMIT 10;"

echo "=== D. newest 6 failed mp3 with context fields ==="
%PSQL% -c "SELECT to_char(j.created_at,'MM-DD HH24:MI:SS') AS created, j.kind, (j.suno_task_id IS NOT NULL) AS has_task, (st.id IS NOT NULL) AS has_ctx, left(coalesce(st.audio_url_ok,''),60) AS ok_url, left(coalesce(st.audio_url_alt,''),60) AS alt_url, left(coalesce(j.error,''),60) AS err FROM stream_upload_jobs j LEFT JOIN suno_tasks st ON st.id = j.suno_task_id WHERE j.status='failed' AND j.kind IN ('mp3_ok','mp3_alt') ORDER BY j.created_at DESC LIMIT 6;"

echo "=== E. oldest 3 failed mp3 with context fields ==="
%PSQL% -c "SELECT to_char(j.created_at,'MM-DD HH24:MI:SS') AS created, j.kind, (j.suno_task_id IS NOT NULL) AS has_task, (st.id IS NOT NULL) AS has_ctx, left(coalesce(st.audio_url_ok,''),60) AS ok_url, left(coalesce(st.audio_url_alt,''),60) AS alt_url, left(coalesce(j.error,''),60) AS err FROM stream_upload_jobs j LEFT JOIN suno_tasks st ON st.id = j.suno_task_id WHERE j.status='failed' AND j.kind IN ('mp3_ok','mp3_alt') ORDER BY j.created_at ASC LIMIT 3;"
'''.replace("%PSQL%", PSQL)


def main() -> int:
    secrets = load_production_secrets()
    host, user, password = resolve_production_ssh(secrets)
    if host != PRODUCTION_HOST:
        raise SystemExit(f"Refusing non-production host: {host}")
    print(f"=== recoverability probe on {host} ===")
    client = ssh_connect(host, user, ensure_deploy_key(), password)
    try:
        guard = "if ! ip -4 addr | grep -q '82.197.71.248'; then exit 1; fi\n"
        _, stdout, stderr = client.exec_command(guard + QUERIES, get_pty=True, timeout=180)
        out = stdout.read().decode("utf-8", errors="replace")
        err = stderr.read().decode("utf-8", errors="replace")
        sys.stdout.buffer.write(out.encode("utf-8", errors="replace") + b"\n")
        if err.strip():
            sys.stderr.write(err[-2000:].encode("utf-8", errors="replace") + b"\n")
        return stdout.channel.recv_exit_status()
    finally:
        client.close()


if __name__ == "__main__":
    raise SystemExit(main())
