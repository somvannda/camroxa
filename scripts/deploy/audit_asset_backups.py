#!/usr/bin/env python3
"""DB audit: which asset backups exist per recent web_music SUCCESS task."""
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

    cols = await pool.fetch(
        "SELECT column_name FROM information_schema.columns WHERE table_name='suno_tasks' "
        "AND (column_name ILIKE '%b2%' OR column_name ILIKE '%wav%' OR column_name ILIKE '%lrc%' "
        "OR column_name ILIKE '%packag%' OR column_name ILIKE '%srt%' OR column_name ILIKE '%encrypt%' "
        "OR column_name ILIKE '%cipher%')"
    )
    print("ASSET COLS:", [c["column_name"] for c in cols])

    rows = await pool.fetch(
        "SELECT id, status, "
        "CASE WHEN b2_storage_key_ok IS NOT NULL AND btrim(b2_storage_key_ok)<>'' THEN 1 ELSE 0 END AS b2ok, "
        "CASE WHEN b2_wav_storage_key_ok IS NOT NULL AND btrim(b2_wav_storage_key_ok)<>'' THEN 1 ELSE 0 END AS wavok, "
        "CASE WHEN b2_lrc_storage_key_ok IS NOT NULL AND btrim(b2_lrc_storage_key_ok)<>'' THEN 1 ELSE 0 END AS lrcok, "
        "CASE WHEN packaged_storage_key_ok IS NOT NULL AND btrim(packaged_storage_key_ok)<>'' THEN 1 ELSE 0 END AS pkgkey, "
        "package_status_ok, wav_status_ok, "
        "CASE WHEN b2_storage_key_alt IS NOT NULL AND btrim(b2_storage_key_alt)<>'' THEN 1 ELSE 0 END AS b2alt, "
        "CASE WHEN b2_wav_storage_key_alt IS NOT NULL AND btrim(b2_wav_storage_key_alt)<>'' THEN 1 ELSE 0 END AS wavalt, "
        "CASE WHEN b2_lrc_storage_key_alt IS NOT NULL AND btrim(b2_lrc_storage_key_alt)<>'' THEN 1 ELSE 0 END AS lrcalt, "
        "package_status_alt, wav_status_alt, updated_at "
        "FROM suno_tasks WHERE source='web_music' AND status='success' "
        "AND updated_at > NOW() - INTERVAL '48 hours' ORDER BY updated_at DESC LIMIT 14"
    )
    for r in rows:
        print({
            "id": str(r["id"])[:8],
            "b2_ok": r["b2ok"], "wav_ok": r["wavok"], "lrc_ok": r["lrcok"], "pkgkey": r["pkgkey"], "pkg": r["package_status_ok"], "wav_st": r["wav_status_ok"],
            "b2_alt": r["b2alt"], "wav_alt": r["wavalt"], "lrc_alt": r["lrcalt"], "pkgA": r["package_status_alt"], "wav_stA": r["wav_status_alt"],
            "upd": str(r["updated_at"]),
        })

    print("\n-- recovery setting --")
    s = await pool.fetchrow("SELECT value FROM system_settings WHERE key='web_music_asset_recovery_v1'")
    print(str(s["value"])[:1200] if s else None)
    await pool.close()

asyncio.run(main())
PYEOF
echo AUDIT_DONE
'''


def main() -> int:
    secrets = load_production_secrets()
    host, user, password = resolve_production_ssh(secrets)
    if host != PRODUCTION_HOST:
        raise SystemExit(f"Refusing non-production host: {host}")
    client = ssh_connect(host, user, ensure_deploy_key(), password)
    try:
        _, stdout, stderr = client.exec_command(REMOTE_CMD, get_pty=False, timeout=150)
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
