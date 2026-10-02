#!/usr/bin/env python3
"""Recent web_music tasks: status/urls/b2/package - find ready-but-not-playable."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DEPLOY = ROOT / "scripts" / "deploy"
sys.path.insert(0, str(DEPLOY / ".venv" / "Lib" / "site-packages"))
sys.path.insert(0, str(DEPLOY))

from deploy import (
    ensure_deploy_key,
    load_production_secrets,
    resolve_production_ssh,
    ssh_connect,
)

PRODUCTION_HOST = "82.197.71.248"

REMOTE_CMD = r'''
set +e
REPO=/opt/camxora/repo/platform_api
cd $REPO && env PYTHONPATH=/opt/camxora/repo .venv/bin/python - <<'PYEOF'
import asyncio, os
import asyncpg

async def main():
    from dotenv import load_dotenv
    load_dotenv("/opt/camxora/repo/platform_api/.env")
    dsn = os.environ.get("PLATFORM_DATABASE_URL")
    if dsn and dsn.startswith("postgresql+asyncpg://"):
        dsn = dsn.replace("postgresql+asyncpg://", "postgresql://", 1)
    pool = await asyncpg.create_pool(dsn, min_size=1, max_size=2)
    rows = await pool.fetch(
        "SELECT t.id, t.status, t.external_task_id, t.error_message, "
        "t.audio_url_ok IS NOT NULL AND btrim(t.audio_url_ok)<>'' AS has_ok, "
        "t.audio_url_alt IS NOT NULL AND btrim(t.audio_url_alt)<>'' AS has_alt, "
        "t.b2_storage_key_ok IS NOT NULL AS has_b2ok, "
        "t.b2_storage_key_alt IS NOT NULL AS has_b2alt, "
        "t.package_status_ok, t.package_status_alt, t.created_at, t.updated_at, u.email "
        "FROM suno_tasks t LEFT JOIN users u ON u.id = t.user_id "
        "WHERE t.source='web_music' ORDER BY t.updated_at DESC LIMIT 12"
    )
    for r in rows:
        print({
            "id": str(r["id"])[:8], "st": r["status"], "ext": (r["external_task_id"] or "")[:12],
            "err": (r["error_message"] or "")[:80], "ok": r["has_ok"], "alt": r["has_alt"],
            "b2ok": r["has_b2ok"], "b2alt": r["has_b2alt"],
            "pkg_ok": r["package_status_ok"], "pkg_alt": r["package_status_alt"],
            "upd": str(r["updated_at"]), "email": r["email"],
        })
    print("\n--- audio url samples (SUCCESS) ---")
    rows2 = await pool.fetch(
        "SELECT id, status, LEFT(audio_url_ok,120) AS ok_url, LEFT(audio_url_alt,120) AS alt_url "
        "FROM suno_tasks WHERE source='web_music' AND status='SUCCESS' "
        "ORDER BY updated_at DESC LIMIT 6"
    )
    for r in rows2:
        print({"id": str(r["id"])[:8], "st": r["status"], "ok_url": r["ok_url"], "alt_url": r["alt_url"]})
    await pool.close()

asyncio.run(main())
PYEOF
echo TASKS_DONE
'''


def main() -> int:
    secrets = load_production_secrets()
    host, user, password = resolve_production_ssh(secrets)
    if host != PRODUCTION_HOST:
        raise SystemExit(f"Refusing non-production host: {host}")
    client = ssh_connect(host, user, ensure_deploy_key(), password)
    try:
        _, stdout, stderr = client.exec_command(REMOTE_CMD, get_pty=False, timeout=120)
        out = stdout.read().decode("utf-8", errors="replace")
        err = stderr.read().decode("utf-8", errors="replace")
        sys.stdout.buffer.write(out.encode("utf-8", errors="replace"))
        if err.strip():
            sys.stderr.write("STDERR: " + err[-1500:] + "\n")
        return 0
    finally:
        client.close()


if __name__ == "__main__":
    raise SystemExit(main())
