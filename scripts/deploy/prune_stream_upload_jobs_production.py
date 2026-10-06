#!/usr/bin/env python3
"""Prune duplicate historical ``stream_upload_jobs`` rows (one per task+variant).

Re-delivered Suno callbacks and desktop reconcile historically inserted many
duplicate job rows per ``(suno_task_id, kind)`` (some tasks carried thousands).
The fix that stops new duplicates is live; this removes the redundant backlog so
admin counts and the table reflect reality.

Keeps exactly one row per ``(suno_task_id, kind)`` for ``mp3_ok`` / ``mp3_alt``,
preferring a successful, B2-backed, newest row. Rows with a NULL ``suno_task_id``
(cover jobs) and ``pending`` rows are never touched; no row is removed if it is
the only one for its task+variant.

Dry-run by default. ``--apply`` first backs the table up with ``pg_dump`` to
``/tmp``, then deletes in batches.

  python scripts/deploy/prune_stream_upload_jobs_production.py
  python scripts/deploy/prune_stream_upload_jobs_production.py --apply
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DEPLOY = ROOT / "scripts" / "deploy"
sys.path.insert(0, str(DEPLOY / ".venv" / "Lib" / "site-packages"))
sys.path.insert(0, str(DEPLOY))

from deploy import ensure_deploy_key, load_production_secrets, resolve_production_ssh, ssh_connect  # noqa: E402

PRODUCTION_HOST = "82.197.71.248"
PSQL = "sudo -u postgres psql -d camxora_platform -P pager=off -t -A"

_RANKED = (
    "WITH ranked AS ("
    "SELECT id, row_number() OVER ("
    "PARTITION BY suno_task_id, kind "
    "ORDER BY (status='success') DESC, "
    "(COALESCE(storage_key,'') <> '') DESC, "
    "created_at DESC, id DESC"
    ") rn "
    "FROM stream_upload_jobs "
    "WHERE kind IN ('mp3_ok','mp3_alt') AND suno_task_id IS NOT NULL)"
)

REMOTE = r'''
set -e
PSQL="%PSQL%"
STAMP="%STAMP%"
CAND="%CAND%"

echo "=== before: totals ==="
$PSQL -c "SELECT 'total=' || count(*) FROM stream_upload_jobs;"
$PSQL -c "SELECT kind, status, count(*) FROM stream_upload_jobs GROUP BY 1,2 ORDER BY 3 DESC;"
$PSQL -c "SELECT 'distinct_task_kind=' || count(*) FROM (SELECT suno_task_id, kind FROM stream_upload_jobs WHERE kind IN ('mp3_ok','mp3_alt') GROUP BY 1,2) x;"
echo "=== fk references pointing TO stream_upload_jobs (must be 0) ==="
$PSQL -c "SELECT count(*) FROM pg_constraint WHERE confrelid = 'stream_upload_jobs'::regclass;"
echo "=== candidates: duplicate mp3 rows beyond the first per task+kind ==="
$PSQL -c "$CAND SELECT count(*) FROM ranked WHERE rn > 1;"

if [ "%APPLY%" != "1" ]; then
  echo "(dry-run: pass --apply to back up and delete)"
else
  echo "=== backup ==="
  sudo -u postgres pg_dump -d camxora_platform -t stream_upload_jobs | gzip > /tmp/stream_upload_jobs_${STAMP}.sql.gz
  ls -lh /tmp/stream_upload_jobs_${STAMP}.sql.gz

  echo "=== deleting in batches ==="
  remaining=$($PSQL -c "$CAND SELECT count(*) FROM ranked WHERE rn > 1;")
  while [ "$remaining" -gt 0 ]; do
    $PSQL -c "DELETE FROM stream_upload_jobs WHERE id IN ($CAND SELECT id FROM ranked WHERE rn > 1 LIMIT 5000);"
    remaining=$($PSQL -c "$CAND SELECT count(*) FROM ranked WHERE rn > 1;")
    echo "remaining_candidates=$remaining"
  done
fi

echo "=== after: totals ==="
$PSQL -c "SELECT 'total=' || count(*) FROM stream_upload_jobs;"
$PSQL -c "SELECT kind, status, count(*) FROM stream_upload_jobs WHERE kind IN ('mp3_ok','mp3_alt') GROUP BY 1,2 ORDER BY 3 DESC;"
$PSQL -c "SELECT 'distinct_task_kind=' || count(*) FROM (SELECT suno_task_id, kind FROM stream_upload_jobs WHERE kind IN ('mp3_ok','mp3_alt') GROUP BY 1,2) x;"
'''.replace("%PSQL%", PSQL).replace("%CAND%", _RANKED)


def main() -> int:
    apply = "--apply" in sys.argv[1:]
    stamp = time.strftime("%Y%m%d-%H%M%S")
    secrets = load_production_secrets()
    host, user, password = resolve_production_ssh(secrets)
    if host != PRODUCTION_HOST:
        raise SystemExit(f"Refusing non-production host: {host}")
    print(f"=== stream_upload_jobs prune on {host} (apply={apply}) ===")
    script = REMOTE.replace("%APPLY%", "1" if apply else "0").replace("%STAMP%", stamp)
    client = ssh_connect(host, user, ensure_deploy_key(), password)
    try:
        guard = "if ! ip -4 addr | grep -q '82.197.71.248'; then exit 1; fi\n"
        _, stdout, stderr = client.exec_command(guard + script, get_pty=True, timeout=1800)
        out = stdout.read().decode("utf-8", errors="replace")
        err = stderr.read().decode("utf-8", errors="replace")
        sys.stdout.buffer.write(out.encode("utf-8", errors="replace") + b"\n")
        if err.strip():
            sys.stderr.write(err[-2500:].encode("utf-8", errors="replace") + b"\n")
        return stdout.channel.recv_exit_status()
    finally:
        client.close()


if __name__ == "__main__":
    raise SystemExit(main())
