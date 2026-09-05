#!/usr/bin/env python3
"""READ-ONLY: validate deployed asset-recovery SQL + progress state on prod.

Calls repo.list_web_music_asset_tasks (the exact deployed method) twice - once
without and once with the moving watermark - to prove the cursor query executes
against the prod schema. Also prints the recovery state row and a small sample
of a scanned task so counters in the state row can be interpreted.
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

PY = r'''
import asyncio, json, os
from pathlib import Path

env_path = Path("/opt/camxora/repo/platform_api/.env")
for line in env_path.read_text(encoding="utf-8").splitlines():
    line = line.strip()
    if not line or line.startswith("#") or "=" not in line:
        continue
    key, _, value = line.partition("=")
    os.environ.setdefault(key.strip(), value.strip())

import asyncpg

async def main():
    dsn = os.environ.get("DATABASE_URL") or os.environ.get("PLATFORM_DATABASE_URL")
    dsn = dsn.replace("postgresql+asyncpg://", "postgresql://")
    conn = await asyncpg.connect(dsn, timeout=10)
    try:
        from platform_api.repositories.streaming_repo import StreamingRepository
        repo = StreamingRepository(conn)

        newest = await repo.list_web_music_asset_tasks(limit=8)
        print("NEWEST_WINDOW_ROWS:", len(newest))
        for row in newest[:3]:
            print("  task=", row["id"], "created=", row["created_at"],
                  "pkg_ok=", row.get("package_status_ok"), "lrc_ok=", row.get("b2_lrc_storage_key_ok"))

        oldest_iso = None
        if newest:
            created = newest[-1]["created_at"]
            oldest_iso = created.isoformat() if hasattr(created, "isoformat") else str(created)
            older = await repo.list_web_music_asset_tasks(limit=8, before=oldest_iso)
            print("OLDER_WINDOW_ROWS(before %s):" % oldest_iso, len(older))
            for row in older[:2]:
                print("  task=", row["id"], "created=", row["created_at"])

        state = await repo.get_asset_recovery_state()
        print("STATE:", json.dumps(state, default=str) if state else None)
    finally:
        await conn.close()

asyncio.run(main())
'''

CMD = r'''
sudo -u camxora env PYTHONPATH=/opt/camxora/repo /opt/camxora/repo/platform_api/.venv/bin/python -B - <<'PY'
%PY%
PY
echo PROBE_ASSET_SQL_DONE
'''
CMD = CMD.replace("%PY%", PY)


def main() -> int:
    secrets = load_production_secrets()
    host, user, password = resolve_production_ssh(secrets)
    if host != PRODUCTION_HOST:
        raise SystemExit(f"Refusing non-production host: {host}")
    print(f"=== read-only asset-recovery SQL probe on {host} ===")
    client = ssh_connect(host, user, ensure_deploy_key(), password)
    try:
        _, stdout, stderr = client.exec_command(CMD, get_pty=True, timeout=120)
        out = stdout.read().decode("utf-8", errors="replace")
        err = stderr.read().decode("utf-8", errors="replace")
        print(out)
        if err.strip():
            print("STDERR:", err[-1500:])
        return stdout.channel.recv_exit_status()
    finally:
        client.close()


if __name__ == "__main__":
    raise SystemExit(main())
