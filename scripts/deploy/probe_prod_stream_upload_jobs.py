#!/usr/bin/env python3
"""READ-ONLY probe of prod stream_upload_jobs visibility gap (200-cap).

Explains why failed mp3_* jobs exist in the DB but do not show up in the admin
upload-jobs list (list is capped at the 200 newest jobs, no pagination).

Run: python scripts/deploy/probe_prod_stream_upload_jobs.py
"""
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
echo "=== 1. all jobs: status x kind ==="
%PSQL% -c "SELECT status, kind, count(*) AS n FROM stream_upload_jobs GROUP BY status, kind ORDER BY status, count(*) DESC;"

echo "=== 2. headline totals ==="
%PSQL% -c "SELECT 'all_jobs_total=' || count(*) FROM stream_upload_jobs;"
%PSQL% -c "SELECT 'failed_any_kind=' || count(*) FROM stream_upload_jobs WHERE status='failed';"
%PSQL% -c "SELECT 'failed_mp3_total=' || count(*) FROM stream_upload_jobs WHERE status='failed' AND kind IN ('mp3_ok','mp3_alt');"

echo "=== 3. failed mp3 visible vs hidden by newest-200 cap ==="
%PSQL% -c "WITH top200 AS (SELECT created_at FROM stream_upload_jobs ORDER BY created_at DESC LIMIT 200), cutoff AS (SELECT min(created_at) AS c FROM top200) SELECT 'failed_mp3_within_newest_200=' || count(*) FILTER (WHERE created_at >= (SELECT c FROM cutoff)), 'failed_mp3_beyond_newest_200=' || count(*) FILTER (WHERE created_at < (SELECT c FROM cutoff)) FROM stream_upload_jobs WHERE status='failed' AND kind IN ('mp3_ok','mp3_alt');"

echo "=== 4. failed mp3 by created month ==="
%PSQL% -c "SELECT to_char(created_at,'YYYY-MM') AS month, count(*) AS n FROM stream_upload_jobs WHERE status='failed' AND kind IN ('mp3_ok','mp3_alt') GROUP BY 1 ORDER BY 1;"

echo "=== 5. oldest & newest failed mp3 ==="
%PSQL% -c "SELECT 'oldest_failed_mp3=' || min(created_at) || ' | newest_failed_mp3=' || max(created_at) FROM stream_upload_jobs WHERE status='failed' AND kind IN ('mp3_ok','mp3_alt');"

echo "=== 6. sample HIDDEN failed mp3 (beyond newest-200), newest 15 ==="
%PSQL% -c "WITH top200 AS (SELECT created_at FROM stream_upload_jobs ORDER BY created_at DESC LIMIT 200), cutoff AS (SELECT min(created_at) AS c FROM top200) SELECT to_char(j.created_at,'YYYY-MM-DD HH24:MI') AS created, j.kind, j.attempt_count AS tries, left(coalesce(j.error,''),90) AS err, left(j.user_id::text,8) AS user_prefix FROM stream_upload_jobs j WHERE j.status='failed' AND j.kind IN ('mp3_ok','mp3_alt') AND j.created_at < (SELECT c FROM cutoff) ORDER BY j.created_at DESC LIMIT 15;"

echo "=== 7. failed mp3 error classification ==="
%PSQL% -c "SELECT count(*) FILTER (WHERE error ILIKE '%404%not found%') AS err_404, count(*) FILTER (WHERE error ILIKE '%no valid suno download url%') AS err_no_suno_url, count(*) FILTER (WHERE error ILIKE '%storage is not configured%') AS err_no_storage, count(*) FILTER (WHERE error ILIKE '%client error%' AND error NOT ILIKE '%404%not found%') AS err_client_other, count(*) FILTER (WHERE error ILIKE '%timed out%' OR error ILIKE '%timeout%' OR error ILIKE '%connection%') AS err_network, count(*) FILTER (WHERE error ILIKE '%403%' OR error ILIKE '%401%' OR error ILIKE '%unauthoriz%') AS err_auth, count(*) FILTER (WHERE error IS NULL OR error='') AS err_null, count(*) FILTER (WHERE error IS NOT NULL AND error<>'' AND NOT (error ILIKE '%404%not found%') AND NOT (error ILIKE '%no valid suno download url%') AND NOT (error ILIKE '%storage is not configured%') AND NOT (error ILIKE '%client error%') AND NOT (error ILIKE '%timed out%' OR error ILIKE '%timeout%' OR error ILIKE '%connection%') AND NOT (error ILIKE '%403%' OR error ILIKE '%401%' OR error ILIKE '%unauthoriz%')) AS err_other FROM stream_upload_jobs WHERE status='failed' AND kind IN ('mp3_ok','mp3_alt');"

echo "=== 8. newest 15 failed mp3 errors (full) ==="
%PSQL% -c "SELECT to_char(j.created_at,'MM-DD HH24:MI:SS') AS created, j.kind, left(coalesce(j.error,''),160) AS err FROM stream_upload_jobs j WHERE j.status='failed' AND j.kind IN ('mp3_ok','mp3_alt') ORDER BY j.created_at DESC LIMIT 15;"

echo "=== 9. does manual retry ever succeed? attempt_count hist ==="
%PSQL% -c "SELECT 'success_after_retry=' || count(*) FILTER (WHERE status='success' AND attempt_count>1), 'failed_after_retry=' || count(*) FILTER (WHERE status='failed' AND attempt_count>1), 'failed_never_retried=' || count(*) FILTER (WHERE status='failed' AND attempt_count<=1) FROM stream_upload_jobs WHERE kind IN ('mp3_ok','mp3_alt');"
'''.replace("%PSQL%", PSQL)


def main() -> int:
    secrets = load_production_secrets()
    host, user, password = resolve_production_ssh(secrets)
    if host != PRODUCTION_HOST:
        raise SystemExit(f"Refusing non-production host: {host}")
    print(f"=== READ-ONLY probe of stream_upload_jobs on {host} ===")
    client = ssh_connect(host, user, ensure_deploy_key(), password)
    try:
        guard = (
            "if ! ip -4 addr | grep -q '82.197.71.248'; then echo Refusing-non-production-host; exit 1; fi\n"
            "if ip -4 addr | grep -q '46.250.235.83'; then echo Refusing-sandbox-host; exit 1; fi\n"
        )
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
