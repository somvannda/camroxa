#!/usr/bin/env python3
"""Production: backfill Xing/Info headers on archived MP3s in Backblaze B2.

Suno CDN MP3s omit the Xing/Info header, so ffprobe and players over-report the
duration and exported MP4s look shorter than the MP3. New uploads are fixed at
archive time; this one-shot sweep re-muxes the MP3s already in B2 so every
desktop client (including older builds) downloads a correctly-labelled file.

Dry-run by default. Pass --apply to re-upload normalized objects.
Optional --limit N caps how many distinct keys are scanned.
"""
from __future__ import annotations

import sys
import time
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

PRODUCTION_HOST = "82.197.71.248"
STAMP = time.strftime("%Y%m%d-%H%M%S")

REMOTE_CMD = r'''
set -e
API=/opt/camxora/repo/platform_api
cd $API
APPLY="%APPLY%" LIMIT="%LIMIT%" PYTHONPATH=/opt/camxora/repo $API/.venv/bin/python - <<'PY'
import asyncio
import os
import sys
from pathlib import Path

sys.path.insert(0, "/opt/camxora/repo")

# Load the API env so platform_api.config resolves the encryption master key.
env_path = Path("/opt/camxora/repo/platform_api/.env")
if env_path.is_file():
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))

import asyncpg  # noqa: E402
from platform_api.services.mp3_duration_header import (  # noqa: E402
    ensure_mp3_duration_header,
    mp3_has_duration_header,
)
from platform_api.services.storage_service import StorageService  # noqa: E402
from platform_api.services.streaming_config_service import (  # noqa: E402
    resolve_streaming_storage_config,
)

APPLY = os.environ.get("APPLY") == "1"
LIMIT = int(os.environ.get("LIMIT") or "0")


async def main() -> None:
    dsn = os.environ.get("PLATFORM_DATABASE_URL", "")
    if dsn.startswith("postgresql+asyncpg://"):
        dsn = dsn.replace("postgresql+asyncpg://", "postgresql://", 1)
    if not dsn:
        print("NO_DSN")
        return
    pool = await asyncpg.create_pool(dsn, min_size=1, max_size=3)
    try:
        config = await resolve_streaming_storage_config(pool)
        if not config.configured:
            print("STORAGE_NOT_CONFIGURED")
            return
        storage = StorageService.from_config(config)

        rows = await pool.fetch(
            """
            SELECT DISTINCT key FROM (
                SELECT b2_storage_key_ok AS key FROM suno_tasks
                  WHERE b2_storage_key_ok IS NOT NULL AND btrim(b2_storage_key_ok) <> ''
                UNION ALL
                SELECT b2_storage_key_alt FROM suno_tasks
                  WHERE b2_storage_key_alt IS NOT NULL AND btrim(b2_storage_key_alt) <> ''
                UNION ALL
                SELECT storage_key FROM stream_tracks
                  WHERE storage_key IS NOT NULL AND btrim(storage_key) <> ''
            ) k
            WHERE key NOT LIKE '%.cxa' AND key NOT LIKE '%.cxo' AND key NOT LIKE '%.wav'
            ORDER BY key
            """
        )
        keys = [str(r["key"]) for r in rows]
        if LIMIT > 0:
            keys = keys[:LIMIT]
        print(f"SCAN_KEYS {len(keys)} apply={APPLY}")

        scanned = skipped = normalized = failed = 0
        for key in keys:
            scanned += 1
            try:
                data = await storage.download_bytes(key)
            except Exception as exc:
                failed += 1
                print(f"  ERR download {key}: {type(exc).__name__} {str(exc)[:120]}")
                continue
            if not data:
                failed += 1
                continue
            if mp3_has_duration_header(data):
                skipped += 1
                continue
            fixed = ensure_mp3_duration_header(data)
            if fixed is data or not mp3_has_duration_header(fixed):
                failed += 1
                print(f"  ERR remux {key}")
                continue
            if APPLY:
                try:
                    await storage.upload_bytes(key=key, data=fixed, content_type="audio/mpeg")
                except Exception as exc:
                    failed += 1
                    print(f"  ERR upload {key}: {type(exc).__name__} {str(exc)[:120]}")
                    continue
            normalized += 1
            if scanned % 25 == 0:
                print(f"  progress scanned={scanned} normalized={normalized}")
        print(
            f"BACKFILL_RESULT scanned={scanned} already_ok={skipped} "
            f"normalized={normalized} failed={failed} apply={APPLY}"
        )
    finally:
        await pool.close()


asyncio.run(main())
PY
echo BACKFILL_DONE
'''

VERIFY_CMD = r'''
cd /opt/camxora/repo
test -f platform_api/services/mp3_duration_header.py && echo HAS_MODULE || echo NO_MODULE
which ffmpeg >/dev/null 2>&1 && echo HAS_FFMPEG || echo NO_FFMPEG
'''


def main() -> int:
    apply = "--apply" in sys.argv
    limit = "0"
    if "--limit" in sys.argv:
        idx = sys.argv.index("--limit")
        if idx + 1 < len(sys.argv):
            limit = sys.argv[idx + 1]

    secrets = load_production_secrets()
    host, user, password = resolve_production_ssh(secrets)
    if host != CANONICAL_PRODUCTION_HOST or host == CANONICAL_SANDBOX_HOST:
        raise SystemExit(f"Refusing non-production host: {host}")
    print(f"=== MP3 duration-header backfill [{'APPLY' if apply else 'DRY-RUN'}] {host} limit={limit} ===")

    client = ssh_connect(host, user, ensure_deploy_key(), password)
    try:
        _, out, _ = client.exec_command(VERIFY_CMD, timeout=60)
        print(out.read().decode("utf-8", errors="replace"))
        cmd = (
            REMOTE_CMD.replace("%APPLY%", "1" if apply else "0")
            .replace("%LIMIT%", str(limit))
            .replace("%STAMP%", STAMP)
        )
        _, stdout, stderr = client.exec_command(cmd, get_pty=False, timeout=3600)
        o = stdout.read().decode("utf-8", errors="replace")
        e = stderr.read().decode("utf-8", errors="replace")
        sys.stdout.buffer.write(o.encode("utf-8", errors="replace"))
        if e.strip():
            sys.stderr.write(e[-3000:] + "\n")
        if "BACKFILL_DONE" not in o:
            print("\nBackfill did not finish cleanly.")
            return 1
        return 0
    finally:
        client.close()


if __name__ == "__main__":
    raise SystemExit(main())
