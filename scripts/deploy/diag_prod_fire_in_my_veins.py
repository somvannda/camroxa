#!/usr/bin/env python3
"""Read-only: inspect Fire in My Veins ok/alt origins on production."""

from __future__ import annotations

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "venv" / "Lib" / "site-packages"))
sys.path.insert(0, str(Path(__file__).resolve().parent / ".venv" / "Lib" / "site-packages"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from deploy import ensure_deploy_key, load_production_secrets, resolve_production_ssh, ssh_connect

PRODUCTION_HOST = "82.197.71.248"

CMD = r"""
set +e
echo '=== Fire in My Veins tasks ==='
sudo -u postgres psql -d camxora_platform -c "
SELECT id,
       round(duration_ok::numeric,2) AS dur_ok,
       round(duration_alt::numeric,2) AS dur_alt,
       b2_storage_key_ok,
       b2_storage_key_alt,
       left(audio_id_ok::text, 12) AS aid_ok,
       left(audio_id_alt::text, 12) AS aid_alt,
       md5(COALESCE(audio_url_ok,'')) AS url_ok_md5,
       md5(COALESCE(audio_url_alt,'')) AS url_alt_md5,
       (audio_url_ok = audio_url_alt) AS urls_equal
FROM suno_tasks
WHERE source = 'web_music' AND title ILIKE '%Fire in My Veins%'
ORDER BY created_at DESC
LIMIT 5;
"
echo '=== colliding untitled keys still? ==='
sudo -u postgres psql -d camxora_platform -c "
SELECT b2_storage_key_ok, count(*) FROM suno_tasks
WHERE source='web_music' AND COALESCE(b2_storage_key_ok,'') <> ''
GROUP BY 1 HAVING count(*) > 1;
"
echo '=== deployed clamp / task scoped ==='
grep -n 'clamp_stream_range\|_usable_web_music_b2_key\|web_music/{user_id}/{suno_task_id' \
  /opt/camxora/repo/platform_api/services/audio_origin_proxy.py \
  /opt/camxora/repo/platform_api/services/web_music_service.py \
  /opt/camxora/repo/platform_api/services/streaming_upload_service.py | head -30
echo '=== B2 object sizes / prefix hashes ==='
sudo -u camxora bash -lc 'set -a && source /opt/camxora/repo/platform_api/.env && set +a && PYTHONPATH=/opt/camxora/repo /opt/camxora/repo/platform_api/.venv/bin/python - <<"PY"
import asyncio, hashlib, os
import asyncpg
from platform_api.services.streaming_config_service import resolve_streaming_storage_config
from platform_api.services.storage_service import StorageService

TASK = "a41873ce-3956-4377-9032-5ac0e5b88ca8"

async def main():
    dsn = os.environ["PLATFORM_DATABASE_URL"].replace("postgresql+asyncpg://", "postgresql://", 1)
    pool = await asyncpg.create_pool(dsn, min_size=1, max_size=2)
    try:
        row = await pool.fetchrow(
            "SELECT b2_storage_key_ok, b2_storage_key_alt FROM suno_tasks WHERE id = $1::uuid",
            TASK,
        )
        config = await resolve_streaming_storage_config(pool)
        storage = StorageService.from_config(config)
        client = storage._client()
        hashes = {}
        for label, key in (("ok", row["b2_storage_key_ok"]), ("alt", row["b2_storage_key_alt"])):
            short = str(key).rsplit("/", 1)[-1]
            head = client.head_object(Bucket=config.bucket, Key=str(key))
            got = client.get_object(Bucket=config.bucket, Key=str(key), Range="bytes=0-65535")
            data = got["Body"].read()
            digest = hashlib.md5(data).hexdigest()
            hashes[label] = digest
            print(label, "name", short, "bytes", head["ContentLength"], "etag", str(head.get("ETag", "")).strip('"')[:16], "prefix_md5", digest, "cr", got.get("ContentRange"))
        print("prefix_equal", hashes.get("ok") == hashes.get("alt"))
    finally:
        await pool.close()

asyncio.run(main())
PY'
echo DIAG_DONE
"""


def run_cmd(client, cmd: str, timeout: int = 40) -> str:
    chan = client.get_transport().open_session()
    chan.settimeout(timeout)
    chan.exec_command(cmd)
    out = b""
    started = time.time()
    while True:
        if chan.recv_ready():
            chunk = chan.recv(65535)
            if not chunk:
                break
            out += chunk
        if chan.exit_status_ready():
            while chan.recv_ready():
                out += chan.recv(65535)
            break
        if time.time() - started > timeout:
            out += b"\nTIMEOUT\n"
            break
        time.sleep(0.1)
    return out.decode("utf-8", errors="replace")


def main() -> int:
    secrets = load_production_secrets()
    host, user, password = resolve_production_ssh(secrets)
    if host != PRODUCTION_HOST:
        raise SystemExit(f"Refusing non-production host: {host}")
    client = ssh_connect(host, user, ensure_deploy_key(), password)
    try:
        print(run_cmd(client, CMD, timeout=35), flush=True)
    finally:
        client.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
