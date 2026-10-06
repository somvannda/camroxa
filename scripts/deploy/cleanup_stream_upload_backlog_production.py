#!/usr/bin/env python3
"""Mark already-archived failed stream upload jobs permanently failed.

Duplicate ``mp3_ok`` / ``mp3_alt`` captures created by re-delivered Suno
callbacks and desktop reconcile accumulate as ``failed`` rows even though the
track is already safely on B2 (2026-10-05 probe: 1405/1406 failed jobs were
archived). The app no longer re-creates them and the health report ignores them,
but the historical rows still inflate the failed count. This marks those rows
``permanent_failed`` so they are terminal and stop counting.

Dry-run by default; pass --apply to write. Read-only until --apply.

Run:
  python scripts/deploy/cleanup_stream_upload_backlog_production.py
  python scripts/deploy/cleanup_stream_upload_backlog_production.py --apply
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

_ARCHIVED = (
    "j.status = 'failed' AND j.kind IN ('mp3_ok', 'mp3_alt') "
    "AND COALESCE(j.permanent_failed, false) = false "
    "AND EXISTS (SELECT 1 FROM stream_tracks t "
    "WHERE t.suno_task_id = j.suno_task_id "
    "AND lower(t.variant) = replace(j.kind, 'mp3_', '') "
    "AND COALESCE(t.storage_key, '') <> '')"
)


def _queries(apply: bool) -> str:
    parts = [
        'echo "=== before ==="',
        f'%PSQL% -c "SELECT \'failed_mp3_not_permanent=\' || count(*) FROM stream_upload_jobs j WHERE {_ARCHIVED};"',
    ]
    if apply:
        parts += [
            'echo "=== applying ==="',
            (
                "%PSQL% -c \"UPDATE stream_upload_jobs j "
                "SET permanent_failed = true, updated_at = NOW() "
                f"WHERE {_ARCHIVED};\""
            ),
        ]
    else:
        parts.append('echo "(dry-run: pass --apply to write)"')
    parts += [
        'echo "=== after ==="',
        (
            '%PSQL% -c "SELECT \'failed_mp3_total=\' || count(*) AS total, '
            '\'failed_mp3_not_permanent=\' || count(*) FILTER (WHERE NOT COALESCE(permanent_failed, false)) AS remaining '
            "FROM stream_upload_jobs WHERE status='failed' AND kind IN ('mp3_ok','mp3_alt');\""
        ),
    ]
    return "\n".join(parts).replace("%PSQL%", PSQL)


def main() -> int:
    apply = "--apply" in sys.argv[1:]
    secrets = load_production_secrets()
    host, user, password = resolve_production_ssh(secrets)
    if host != PRODUCTION_HOST:
        raise SystemExit(f"Refusing non-production host: {host}")
    print(f"=== stream upload backlog cleanup on {host} (apply={apply}) ===")
    client = ssh_connect(host, user, ensure_deploy_key(), password)
    try:
        guard = "if ! ip -4 addr | grep -q '82.197.71.248'; then exit 1; fi\n"
        _, stdout, stderr = client.exec_command(guard + _queries(apply), get_pty=True, timeout=300)
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
