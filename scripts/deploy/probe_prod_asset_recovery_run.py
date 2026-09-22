#!/usr/bin/env python3
"""Functional probe: run ONE web-music asset recovery pass on prod and report.

Triggers exactly one pass via the deployed service (same code path as the
admin endpoint + auto loop; advisory-lock guard makes concurrent starts safe),
waits briefly, then prints the DB-backed counters/errors row again.

Cost ceiling: 1 pass = up to 8 tasks, 2 WAV conversions, 6 LRC, SRT derivation,
encrypted packages. This is the same gentle budget the auto loop uses.
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
WAIT_S = 30
PSQL = "sudo -u postgres psql -d camxora_platform -P pager=off -t -A"

PY = r'''
import asyncio, os
from pathlib import Path

env_path = Path("/opt/camxora/repo/platform_api/.env")
if env_path.is_file():
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip())

from platform_api.dependencies import get_db_pool
from platform_api.services.streaming_upload_service import StreamingUploadService

async def main():
    pool = await get_db_pool()
    service = StreamingUploadService(pool)
    try:
        result = await service.start_web_music_asset_recovery()
        print("START_RESULT:", result)
    finally:
        await pool.close()

asyncio.run(main())
'''

CMD = r'''
%PSQL% -c "SELECT 'STATE_BEFORE=' || COALESCE(value,'<none>') FROM system_settings WHERE key='web_music_asset_recovery_v1';"

echo "--- starting one recovery pass ---"
sudo -u camxora env PYTHONPATH=/opt/camxora/repo /opt/camxora/repo/platform_api/.venv/bin/python -B - <<'PY'
%PY%
PY

echo "--- waiting %WAIT_S% seconds ---"
sleep %WAIT_S%

%PSQL% -c "SELECT 'STATE_AFTER=' || COALESCE(value,'<none>') FROM system_settings WHERE key='web_music_asset_recovery_v1';"

echo "--- recent suno_tasks with recovered srt/package keys (sample) ---"
%PSQL% -c "SELECT 'sample=' || id || '|pkg_ok=' || COALESCE(package_status_ok,'-') || '|srt_ok=' || COALESCE(b2_lrc_storage_key_ok,'-') FROM suno_tasks WHERE COALESCE(b2_storage_key_ok,'')<>'' ORDER BY created_at DESC LIMIT 1;"
echo PROBE_ASSET_RECOVERY_DONE
'''

CMD = CMD.replace("%PY%", PY).replace("%WAIT_S%", str(WAIT_S)).replace("%PSQL%", PSQL)


def main() -> int:
    secrets = load_production_secrets()
    host, user, password = resolve_production_ssh(secrets)
    if host != PRODUCTION_HOST:
        raise SystemExit(f"Refusing non-production host: {host}")
    print(f"=== trigger + observe asset recovery pass on {host} ===")
    client = ssh_connect(host, user, ensure_deploy_key(), password)
    try:
        _, stdout, stderr = client.exec_command(CMD, get_pty=True, timeout=300)
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
